"""Simulation engine: clock, telemetry and fault injection.

Time is measured in simulated minutes since `start`. Each tick advances the
clock by (real seconds × speed) and updates every component's telemetry
from simple physical models (thermal, battery, packet loss, ECC, disks).
"""
from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from .topology import (COOLING_EFF, THERMAL_K, THERMAL_LIMIT, THERMAL_SHUTDOWN,
                       Eff, Forecast, Own, Topology, thermal_equilibrium)

SIM_START = datetime(2026, 11, 8, 5, 30)  # 30 min before the 06:00 shift change
CHECKPOINT_EVERY_MIN = 45

_fault_ids = itertools.count(1)


@dataclass
class Fault:
    id: str
    preset: str
    target: str
    started: float
    label: str = ""
    repair_at: Optional[float] = None
    expires: Optional[float] = None  # noise faults clear themselves
    params: dict = field(default_factory=dict)

    def to_dict(self, now: float):
        return {
            "id": self.id, "preset": self.preset, "target": self.target,
            "label": self.label, "age_min": round(now - self.started, 1),
            "repair_in": round(self.repair_at - now, 1) if self.repair_at else None,
        }


NOISE = [
    ("storage", "warn", "SMART pre-fail warning on 1 disk (reallocated sectors)"),
    ("crac", "info", "CRAC fan speed variance above 8%"),
    ("leaf", "warn", "CRC errors on one access port (recovered)"),
    ("gpu_node", "info", "Single correctable ECC burst (below threshold)"),
    ("spine", "info", "BGP session reset to peer, re-established in 4s"),
    ("ups", "info", "UPS self-test completed with battery string warning"),
]

REPAIR_MIN = {"cooling_failure": 9, "power_feed_loss": 6, "tor_flapping": 3,
              "storage_degradation": 7, "gpu_ecc": 4, "maintenance": 0}


class Simulator:
    def __init__(self, topo: Topology, emit: Callable[..., None], seed: int = 7):
        self.topo = topo
        self.emit = emit
        self.rng = random.Random(seed)
        self.now = 0.0
        self.speed = 10.0
        self.paused = False
        self.faults: dict[str, Fault] = {}
        self.metrics: dict[str, dict] = {}
        self.own: dict[str, Own] = {}
        self.eff: dict[str, Eff] = {}
        self.next_noise = 12.0
        self.noise_enabled = True
        self._init_metrics()
        self._compute_own()
        self.eff = topo.propagate(self.own, self.metrics)

    # ---------------------------------------------------------------- clock
    def clock_dt(self, t: Optional[float] = None) -> datetime:
        return SIM_START + timedelta(minutes=self.now if t is None else t)

    def iso(self, t: Optional[float] = None) -> str:
        return self.clock_dt(t).isoformat(timespec="seconds")

    # ------------------------------------------------------------- metrics
    def _init_metrics(self):
        r = self.rng
        for nid, n in self.topo.nodes.items():
            k = n["kind"]
            if k == "power_feed":
                m = {"voltage_v": 480.0, "load_kw": r.uniform(900, 1200)}
            elif k == "ups":
                m = {"load_pct": r.uniform(42, 58), "battery_pct": 100.0, "on_battery": False}
            elif k == "chiller":
                m = {"supply_c": 7.0, "return_c": 13.0}
            elif k == "crac":
                m = {"supply_air_c": 18.0, "fan_pct": r.uniform(55, 65)}
            elif k in ("spine", "leaf"):
                m = {"util_pct": r.uniform(30, 60), "loss_pct": 0.01, "flaps": 0}
            elif k == "rack":
                m = {"inlet_c": r.uniform(24.0, 25.5), "power_kw": r.uniform(34, 42), "load": 0.8}
            elif k == "gpu_node":
                m = {"temp_c": 62.0, "util_pct": 0.0, "ecc_rate": r.uniform(0, 2), "xid": 0,
                     "gpus_healthy": n["gpus_total"]}
            elif k == "storage":
                m = {"latency_ms": r.uniform(2.5, 4), "failed_disks": 0, "health_pct": 100.0,
                     "iops_k": r.uniform(180, 260), "rebuild_pct": None}
            elif k == "workload":
                if n["wtype"] == "inference":
                    m = {"qps": float(n.get("qps", 1000)), "p99_ms": float(n.get("base_p99_ms", 150)),
                         "error_pct": 0.05, "traffic_pct": 100.0}
                else:
                    m = {"throughput_pct": 100.0, "step": r.randint(20000, 60000),
                         "last_ckpt": -r.uniform(8, 40), "state": "running", "lost_min": 0.0}
            else:
                m = {}
            self.metrics[nid] = m

    # -------------------------------------------------------------- faults
    def inject(self, preset: str, target: str, label: str = "") -> Fault:
        f = Fault(id=f"F{next(_fault_ids)}", preset=preset, target=target,
                  started=self.now, label=label or preset)
        if preset == "storage_degradation":
            self.metrics[target]["failed_disks"] = 2
            self.metrics[target]["rebuild_pct"] = 0.0
            f.params["escalate_at"] = self.now + 30
        if preset == "gpu_ecc":
            f.params["fail_at"] = self.now + 20
        self.faults[f.id] = f
        return f

    def clear_fault(self, fid: str):
        f = self.faults.pop(fid, None)
        if not f:
            return None
        m = self.metrics.get(f.target, {})
        if f.preset == "storage_degradation":
            m.update(failed_disks=0, rebuild_pct=None, health_pct=100.0)
        if f.preset == "gpu_ecc":
            m.update(ecc_rate=1.0, xid=0, gpus_healthy=self.topo.nodes[f.target]["gpus_total"])
        if f.preset == "tor_flapping":
            m.update(flaps=0)
        return f

    def faults_on(self, nid: str) -> list[Fault]:
        return [f for f in self.faults.values() if f.target == nid]

    # ---------------------------------------------------------------- tick
    def tick(self, dt: float):
        """Advance dt simulated minutes."""
        if dt <= 0:
            return
        self.now += dt
        self._progress_faults()
        self._maybe_noise()
        self._update_metrics(dt)
        self._compute_own()
        self.eff = self.topo.propagate(self.own, self.metrics)
        self._workload_lifecycle()

    def _progress_faults(self):
        for f in list(self.faults.values()):
            if f.expires is not None and self.now >= f.expires:
                self.faults.pop(f.id, None)
                continue
            if f.repair_at is not None and self.now >= f.repair_at:
                self.clear_fault(f.id)
                self.emit("fault_cleared", f"Repair complete: {self.topo.nodes[f.target]['name']} "
                          f"({self.topo.nodes[f.target]['region']}) back in service",
                          severity="success", node=f.target)
                continue
            if f.preset == "storage_degradation" and not f.params.get("escalated") \
                    and self.now >= f.params["escalate_at"]:
                f.params["escalated"] = True
                self.metrics[f.target]["failed_disks"] = 3
                self.emit("fault_progressed", f"{self.topo.nodes[f.target]['name']}: third disk failed — "
                          "placement groups inactive, cluster READ-ONLY", severity="crit", node=f.target)
            if f.preset == "gpu_ecc" and not f.params.get("failed") and self.now >= f.params["fail_at"]:
                f.params["failed"] = True
                self.metrics[f.target]["xid"] = 79
                self.emit("fault_progressed", f"{self.topo.nodes[f.target]['name']}: XID 79 — GPU has "
                          "fallen off the bus", severity="crit", node=f.target)

    def _maybe_noise(self):
        if not self.noise_enabled or self.now < self.next_noise:
            return
        self.next_noise = self.now + self.rng.uniform(14, 26)
        kind, sev, msg = self.rng.choice(NOISE)
        busy = {f.target for f in self.faults.values()}
        candidates = [n for n in self.topo.nodes.values() if n["kind"] == kind and n["id"] not in busy]
        if not candidates:
            return
        n = self.rng.choice(candidates)
        f = Fault(id=f"F{next(_fault_ids)}", preset="noise", target=n["id"], started=self.now,
                  label=msg, expires=self.now + self.rng.uniform(4, 9), params={"severity": sev})
        self.faults[f.id] = f

    def _dep_sources(self, nid: str, dtype: str) -> list[str]:
        out = []
        for d in self.topo._deps_into[nid]:
            if d.type == dtype:
                out += d.sources
        return out

    def _update_metrics(self, dt: float):
        r = self.rng
        jitter = lambda x, s: x + r.uniform(-s, s)
        fault_by_target: dict[str, list[Fault]] = {}
        for f in self.faults.values():
            fault_by_target.setdefault(f.target, []).append(f)

        for nid, n in self.topo.nodes.items():
            m = self.metrics[nid]
            k = n["kind"]
            presets = {f.preset for f in fault_by_target.get(nid, [])}
            e = self.eff.get(nid, Eff())
            if k == "power_feed":
                m["voltage_v"] = 0.0 if ("power_feed_loss" in presets or "maintenance" in presets) else jitter(480, 2)
            elif k == "ups":
                srcs = self._dep_sources(nid, "power")
                on_batt = any(self.eff.get(s, Eff()).status == "down" for s in srcs)
                m["on_battery"] = on_batt
                if on_batt:
                    m["battery_pct"] = max(0.0, m["battery_pct"] - dt * 100.0 / n.get("runtime_min", 15))
                else:
                    m["battery_pct"] = min(100.0, m["battery_pct"] + dt * 100.0 / 90.0)
                m["load_pct"] = jitter(50, 3)
            elif k == "chiller":
                broken = "cooling_failure" in presets or "maintenance" in presets or e.status == "down"
                target = 17.0 if broken else 7.0
                m["supply_c"] += (target - m["supply_c"]) * min(1.0, 0.3 * dt)
                m["return_c"] = m["supply_c"] + 6
            elif k == "crac":
                bad = e.status in ("degraded", "down")
                target = 29.0 if bad else 18.0
                m["supply_air_c"] += (target - m["supply_air_c"]) * min(1.0, 0.25 * dt)
                m["fan_pct"] = 0.0 if e.status == "down" else (100.0 if bad else jitter(60, 3))
            elif k in ("spine", "leaf"):
                if "tor_flapping" in presets:
                    m["loss_pct"] = r.uniform(2.0, 8.0)
                    m["flaps"] += r.randint(1, 4)
                elif e.status == "down":
                    m["loss_pct"] = 100.0
                else:
                    m["loss_pct"] = max(0.0, jitter(0.01, 0.01))
                    m["flaps"] = max(0, m["flaps"] - 1)
                m["util_pct"] = min(99, max(5, jitter(m["util_pct"], 1.5)))
            elif k == "rack":
                crac = self._dep_sources(nid, "cooling")
                crac_status = self.eff.get(crac[0], Eff()).status if crac else "ok"
                if e.status == "down" and self.own.get(nid, Own()).status == "down":
                    load = 0.05  # thermal shutdown, servers off
                else:
                    load = 0.8
                m["load"] = load
                teq = thermal_equilibrium(COOLING_EFF[crac_status], load)
                m["inlet_c"] = teq - (teq - m["inlet_c"]) * math.exp(-THERMAL_K * dt) + r.uniform(-0.05, 0.05)
                m["power_kw"] = jitter(38 * load / 0.8, 0.8)
            elif k == "gpu_node":
                rack_m = self.metrics.get(n["rack"], {})
                used = self.topo.gpu_used(nid)
                util = 0.0 if e.status == "down" else min(100.0, 100.0 * used / n["gpus_total"] * r.uniform(0.9, 1.0))
                m["util_pct"] = util
                m["temp_c"] = rack_m.get("inlet_c", 25) + 20 + util * 0.25 + r.uniform(-0.5, 0.5)
                if "gpu_ecc" in presets:
                    f = next(f for f in fault_by_target[nid] if f.preset == "gpu_ecc")
                    age = self.now - f.started
                    m["ecc_rate"] = 40 + age * 18 + r.uniform(0, 10)
                    m["gpus_healthy"] = n["gpus_total"] - (8 if f.params.get("failed") else 0)
                else:
                    m["ecc_rate"] = max(0.0, jitter(1.0, 1.0))
            elif k == "storage":
                if "storage_degradation" in presets:
                    f = next(f for f in fault_by_target[nid] if f.preset == "storage_degradation")
                    m["rebuild_pct"] = min(95.0, (self.now - f.started) * 2.2)
                    m["latency_ms"] = r.uniform(18, 32) if not f.params.get("escalated") else r.uniform(80, 140)
                    m["health_pct"] = 100 - m["failed_disks"] * 9
                else:
                    m["latency_ms"] = r.uniform(9, 14) if e.status in ("degraded", "down") else jitter(3.2, 0.6)
            elif k == "workload":
                self._workload_metrics(n, m, e)

    def _workload_metrics(self, n: dict, m: dict, e: Eff):
        r = self.rng
        st = e.status
        if n["wtype"] == "inference":
            base = float(n.get("base_p99_ms", 150))
            share = m.get("traffic_pct", 100.0) / 100.0
            if st == "down":
                m.update(p99_ms=0.0, error_pct=100.0, qps=0.0)
            elif st == "degraded":
                m.update(p99_ms=base * r.uniform(1.7, 2.6), error_pct=r.uniform(2, 7),
                         qps=float(n.get("qps", 1000)) * share * r.uniform(0.8, 0.95))
            else:
                extra = n.get("_latency_add_ms", 0)
                m.update(p99_ms=base * r.uniform(0.95, 1.08) + extra, error_pct=r.uniform(0.01, 0.1),
                         qps=float(n.get("qps", 1000)) * share * r.uniform(0.95, 1.05))
        else:
            if m["state"] == "running":
                m["throughput_pct"] = 100.0 * r.uniform(0.96, 1.0) if st in ("ok", "at_risk") else r.uniform(40, 65)
                m["step"] += int(12 * m["throughput_pct"] / 100)
                if self.now - m["last_ckpt"] >= CHECKPOINT_EVERY_MIN:
                    m["last_ckpt"] = self.now
            else:
                m["throughput_pct"] = 0.0

    def _compute_own(self):
        own: dict[str, Own] = {}
        for nid, n in self.topo.nodes.items():
            o = Own()
            m = self.metrics[nid]
            k = n["kind"]
            for f in self.faults_on(nid):
                if f.preset == "maintenance":
                    o = Own("down", None, "planned maintenance", maintenance=True)
                elif f.preset == "cooling_failure":
                    o = Own("down", None, "compressor fault" if k == "chiller" else "unit failure")
                elif f.preset == "power_feed_loss":
                    o = Own("down", None, "utility feed lost; generator failed to start")
                elif f.preset == "tor_flapping":
                    o = Own("degraded", None, f"uplinks flapping ({m.get('loss_pct', 0):.1f}% loss)")
                elif f.preset == "storage_degradation":
                    if f.params.get("escalated"):
                        o = Own("down", None, "cluster read-only (3 OSDs down)")
                    else:
                        o = Own("degraded", Forecast("down", max(0.0, f.params["escalate_at"] - self.now),
                                                     "read-only if another disk fails"),
                                "2 OSDs down, rebuilding")
                elif f.preset == "gpu_ecc":
                    if f.params.get("failed"):
                        o = Own("down", None, "XID 79: GPU fell off the bus")
                    else:
                        o = Own("degraded", Forecast("down", max(0.0, f.params["fail_at"] - self.now),
                                                     "GPU expected to fall off the bus"),
                                "ECC error storm")
            if k == "ups" and m["battery_pct"] <= 0.0 and o.status == "ok":
                o = Own("down", None, "battery exhausted")
            if k == "rack" and o.status != "down":
                t = m["inlet_c"]
                if t >= THERMAL_SHUTDOWN:
                    o = Own("down", None, f"thermal shutdown ({t:.1f}°C inlet)")
                elif t >= THERMAL_LIMIT:
                    o = Own("degraded", None, f"thermal throttling ({t:.1f}°C inlet)")
            own[nid] = o
        self.own = own

    def _workload_lifecycle(self):
        for nid, n in self.topo.nodes.items():
            if n["kind"] != "workload" or n["wtype"] != "training":
                continue
            m = self.metrics[nid]
            st = self.eff[nid].status
            if n.get("_migrating"):
                continue
            if m["state"] == "running" and st == "down":
                lost = self.now - m["last_ckpt"]
                m["state"] = "crashed"
                m["lost_min"] += lost
                self.emit("job_crashed", f"{n['name']} crashed — lost {lost:.0f} min of training since "
                          "last checkpoint", severity="crit", node=nid)
            elif m["state"] == "crashed" and st in ("ok", "at_risk"):
                m["state"] = "running"
                self.emit("job_restarted", f"{n['name']} auto-restarted from last checkpoint",
                          severity="success", node=nid)

    # ------------------------------------------------------------ snapshot
    def node_snapshot(self) -> dict:
        out = {}
        for nid in self.topo.nodes:
            e = self.eff[nid]
            o = self.own[nid]
            m = self.metrics[nid]
            out[nid] = {
                **e.to_dict(),
                "own": o.status,
                "maintenance": o.maintenance,
                "metrics": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()},
            }
        return out
