"""Engine: owns all state and advances the world one tick at a time."""
from __future__ import annotations

import asyncio
import copy
import itertools
from typing import Optional

import yaml

from . import reports
from .incidents import IncidentManager, Roster
from .llm import LLM
from .migrations import MigrationPlanner
from .simulation import Simulator
from .topology import DATA_DIR, SEV, Own, Topology, compress_names

SPEEDS = [1, 10, 30, 60, 120]
KIND_LABEL = {"power_feed": "Feed", "ups": "UPS", "chiller": "Chiller", "crac": "CRAC", "spine": "Spine",
              "leaf": "Leaf", "rack": "Rack", "gpu_node": "GPU node", "storage": "Storage", "workload": "Workload"}


class Engine:
    def __init__(self):
        self.llm = LLM()
        self.reset()

    # ------------------------------------------------------------- set-up
    def reset(self):
        from . import incidents as _inc, migrations as _mig, simulation as _sim
        _inc._alert_ids, _inc._incident_ids = itertools.count(1), itertools.count(1001)
        _mig._mig_ids = itertools.count(101)
        _sim._fault_ids = itertools.count(1)
        reports._handoff_ids, reports._item_ids = itertools.count(1), itertools.count(1)
        self._ev_ids = itertools.count(1)
        self.timeline: list[dict] = []
        self.fault_history: list[dict] = []
        self.handoffs: list[dict] = []
        self.incidents = None  # set below; emit() checks it
        self.topo = Topology.load()
        self.roster = Roster()
        self.runbooks = yaml.safe_load((DATA_DIR / "runbooks.yaml").read_text())
        self.sim = Simulator(self.topo, self.emit)
        self.incidents = IncidentManager(self)
        self.planner = MigrationPlanner(self)
        self._shift_id = self.current_shift()["id"]
        self.emit("system", f"Simulation started — {self.current_shift()['name']} on duty "
                  f"({', '.join(e['name'] for e in self.roster.on_shift(self._shift_id))})", severity="info")

    # -------------------------------------------------------------- events
    def emit(self, kind: str, message: str, severity: str = "info", node: Optional[str] = None,
             incident: Optional[str] = None, actor: str = "system"):
        if incident is None and node and self.incidents is not None:
            inc = self.incidents.incident_for_node(node)
            incident = inc.id if inc else None
        ev = {
            "id": next(self._ev_ids), "t": self.sim.iso() if hasattr(self, "sim") else "",
            "t_min": round(self.sim.now, 2) if hasattr(self, "sim") else 0, "kind": kind,
            "severity": severity, "message": message, "node": node, "incident": incident, "actor": actor,
            "actor_name": self.roster.engineers.get(actor, {}).get("name", actor) if hasattr(self, "roster") else actor,
            "region": self.topo.nodes[node]["region"] if node and node in self.topo.nodes else None,
        }
        self.timeline.append(ev)
        if len(self.timeline) > 4000:
            self.timeline = self.timeline[-3000:]

    # --------------------------------------------------------------- shift
    def current_shift(self) -> dict:
        dt = self.sim.clock_dt()
        return self.roster.shift_at(dt.hour * 60 + dt.minute + dt.second / 60)

    def shift_info(self) -> dict:
        s = self.current_shift()
        dt = self.sim.clock_dt()
        mod = dt.hour * 60 + dt.minute + dt.second / 60
        end = Roster._mins(s["end"])
        until = (end - mod) % 1440
        return {**s, "next_change_in_min": round(until, 1),
                "lead": (self.roster.lead(s["id"]) or {}).get("name")}

    def _check_shift_change(self):
        s = self.current_shift()
        if s["id"] == self._shift_id:
            return
        prev = next(x for x in self.roster.shifts if x["id"] == self._shift_id)
        self._shift_id = s["id"]
        self.emit("shift_change", f"Shift change: {prev['name']} → {s['name']} "
                  f"(lead {(self.roster.lead(s['id']) or {}).get('name', '—')})", severity="warn")
        self.incidents.reroute_for_shift()
        self.create_handoff(prev, s, reason="scheduled shift change")

    def create_handoff(self, prev: dict, nxt: dict, reason: str) -> dict:
        report = reports.build_handoff(self, prev, nxt, reason)
        self.handoffs.insert(0, report)
        self.emit("handoff_created", f"{report['id']} handoff report: {len(report['items'])} items for "
                  f"{nxt['name']} to acknowledge", severity="info")
        self._spawn(reports.generate_handoff_narrative(self, report))
        return report

    def _check_handoff_overdue(self):
        for r in self.handoffs:
            if r["complete"] or r["overdue_notified"]:
                continue
            if self.sim.now - r["created_min"] >= 15:
                r["overdue_notified"] = True
                pending = sum(1 for i in r["items"] if not i["acked_by"])
                self.emit("escalated", f"{r['id']}: {pending} handoff item(s) unacknowledged after 15 min — "
                          f"escalated to {r['incoming_lead']}", severity="crit")

    # ---------------------------------------------------------------- tick
    def step(self, dt: float):
        remaining = dt
        while remaining > 1e-9:
            d = min(0.25, remaining)
            remaining -= d
            self.sim.tick(d)
            self.incidents.tick()
            self.planner.tick()
            self._check_shift_change()
            self._check_handoff_overdue()

    def _spawn(self, coro):
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            coro.close()

    def request_summary(self, inc_id: str):
        self._spawn(reports.generate_summary(self, inc_id))

    # ---------------------------------------------------------- blast radius
    def blast_radius(self, sources: list[str], mode: str = "auto") -> dict:
        sim, topo = self.sim, self.topo
        sources = [s for s in sources if s in topo.nodes]
        if not sources:
            return {}
        if mode == "auto":
            mode = "live" if all(sim.own[s].status != "ok" or sim.own[s].forecast for s in sources) else "hypothetical"
        desc: set[str] = set()
        for s in sources:
            desc |= topo.descendants(s)
        desc -= set(sources)
        if mode == "live":
            eff = sim.eff
            affected_ids = [n for n in desc if eff[n].status != "ok" or eff[n].forecast]
        else:
            own = copy.copy(sim.own)
            for s in sources:
                own[s] = Own("down", None, "taken down (what-if)", maintenance=True)
            eff = topo.propagate(own, sim.metrics)
            live = sim.eff
            affected_ids = []
            for n in desc:
                a, b = eff[n], live[n]
                worse_now = SEV[a.status] > SEV[b.status]
                worse_fc = a.forecast and (not b.forecast or a.forecast.eta < b.forecast.eta - 0.5
                                           or SEV[a.forecast.status] > SEV[b.forecast.status])
                if worse_now or worse_fc:
                    affected_ids.append(n)

        affected = []
        for n in affected_ids:
            node, ef = topo.nodes[n], eff[n]
            eta = 0.0 if SEV[ef.status] >= SEV["degraded"] else (ef.forecast.eta if ef.forecast else None)
            affected.append({"id": n, "name": node["name"], "kind": node["kind"], "region": node["region"],
                             "status": ef.status, "forecast": ef.forecast.to_dict() if ef.forecast else None,
                             "eta": round(eta, 1) if eta is not None else None})
        affected.sort(key=lambda x: (-SEV[x["status"]], x["eta"] if x["eta"] is not None else 999))

        workloads, customers = [], {}
        for a in affected:
            if a["kind"] != "workload":
                continue
            w = topo.nodes[a["id"]]
            c = topo.customers.get(w["customer"], {})
            impact = a["status"] if a["status"] != "ok" else (a["forecast"]["status"] if a["forecast"] else "at_risk")
            workloads.append({"id": a["id"], "name": w["name"], "customer": c.get("name", w["customer"]),
                              "tier": c.get("tier", "silver"), "sla": c.get("sla"), "type": w["wtype"],
                              "status": a["status"], "impact": impact, "eta": a["eta"], "region": a["region"]})
            cc = customers.setdefault(c.get("id", w["customer"]), {
                "name": c.get("name", w["customer"]), "tier": c.get("tier"), "sla": c.get("sla"),
                "penalty_per_hour": c.get("penalty_per_hour", 0), "workloads": []})
            cc["workloads"].append(w["name"])

        # human statements, e.g. "Racks B4–B9 reach thermal limit (35°C) in ~12 min"
        groups: dict[tuple, list[dict]] = {}
        for a in affected:
            if a["kind"] in ("gpu_node",):
                continue
            if a["status"] in ("degraded", "down"):
                key = (a["kind"], "now", a["status"], "")
            elif a["forecast"]:
                key = (a["kind"], "forecast", a["forecast"]["status"], a["forecast"]["reason"])
            else:
                key = (a["kind"], "risk", "at_risk", eff[a["id"]].reason)
            groups.setdefault(key, []).append(a)
        statements, order = [], []
        for (kind, when, status, reason), items in groups.items():
            names = sorted(i["name"] for i in items)
            if kind == "rack":
                label = compress_names(names)
            elif len(names) <= 3:
                label = ", ".join(names)
            else:
                label = f"{len(names)} {KIND_LABEL.get(kind, kind).lower()}s"
            if when == "now":
                text, sort_eta = f"{label} {status.replace('_', ' ')} now", -1
            elif when == "forecast":
                lo = min(i["forecast"]["eta"] for i in items)
                hi = max(i["forecast"]["eta"] for i in items)
                span = f"~{lo:.0f} min" if round(hi) - round(lo) < 1 else f"~{lo:.0f}–{hi:.0f} min"
                if kind == "rack":
                    text = f"{label} {reason} in {span}"
                elif kind == "workload":
                    text = f"{label} impacted in {span} — {reason}"
                else:
                    text = f"{label} {status.replace('_', ' ')} in {span} — {reason}"
                sort_eta = lo
            else:
                text, sort_eta = f"{label} at risk" + (f" — {reason}" if reason else ""), 9999
            order.append((sort_eta, kind != "rack", text))
        statements = [t for _, _, t in sorted(order)]
        etas = [a["eta"] for a in affected if a["eta"] is not None]
        regions = sorted({a["region"] for a in affected} | {topo.nodes[s]["region"] for s in sources})
        counts = {s: sum(1 for a in affected if a["status"] == s) for s in ("at_risk", "degraded", "down")}
        counts["at_risk"] += sum(1 for a in affected if a["status"] == "ok")
        return {
            "mode": mode, "sources": sources, "source_names": [topo.nodes[s]["name"] for s in sources],
            "affected": affected, "counts": counts, "workloads": workloads,
            "customers": list(customers.values()), "statements": statements[:8],
            "earliest_eta": round(min(etas), 1) if etas else None, "regions": regions,
            "cross_region": len(regions) > 1,
            "penalty_per_hour": sum(c["penalty_per_hour"] for c in customers.values()),
        }

    # ------------------------------------------------------------- actions
    def inject(self, preset: str, target: Optional[str], actor: str = "operator") -> dict:
        p = next((x for x in self.topo.presets if x["id"] == preset), None)
        if not p:
            raise ValueError(f"unknown preset {preset}")
        target = target or p["default_target"]
        n = self.topo.nodes.get(target)
        if not n or n["kind"] not in p["kinds"]:
            raise ValueError(f"{target} is not a valid target for {preset}")
        if any(f.preset == preset for f in self.sim.faults_on(target)):
            raise ValueError(f"{preset} already active on {target}")
        f = self.sim.inject(preset, target, label=p["name"])
        self.fault_history.append({"id": f.id, "preset": preset, "target": target, "t": self.sim.iso(),
                                   "description": p["description"]})
        self.emit("fault_injected", f"[sim] Injected '{p['name']}' on {n['name']} ({n['region']}) — "
                  f"{p['description']}", severity="warn", node=target, actor="simulator")
        return f.to_dict(self.sim.now)

    def start_maintenance(self, nodes: list[str], actor: str) -> list[str]:
        started = []
        for nid in nodes:
            if nid in self.topo.nodes and not any(f.preset == "maintenance" for f in self.sim.faults_on(nid)):
                self.sim.inject("maintenance", nid, label="Planned maintenance")
                started.append(nid)
        if started:
            names = ", ".join(self.topo.nodes[n]["name"] for n in started)
            self.emit("maintenance_started", f"Maintenance started on {names} by "
                      f"{self.roster.engineers.get(actor, {}).get('name', actor)} — affected workloads will be "
                      "migrated", severity="warn", actor=actor)
        return started

    def end_maintenance(self, actor: str):
        ended = [f for f in list(self.sim.faults.values()) if f.preset == "maintenance"]
        for f in ended:
            self.sim.clear_fault(f.id)
        if ended:
            self.emit("maintenance_ended", "Maintenance complete: " + ", ".join(
                self.topo.nodes[f.target]["name"] for f in ended), severity="success", actor=actor)

    def manual_handoff(self, actor: str) -> dict:
        cur = self.current_shift()
        idx = [s["id"] for s in self.roster.shifts].index(cur["id"])
        nxt = self.roster.shifts[(idx + 1) % len(self.roster.shifts)]
        return self.create_handoff(cur, nxt, reason=f"preview requested by "
                                   f"{self.roster.engineers.get(actor, {}).get('name', actor)}")

    def ack_handoff_item(self, hid: str, item_id: str, actor: str) -> dict:
        r = next(h for h in self.handoffs if h["id"] == hid)
        it = next(i for i in r["items"] if i["id"] == item_id)
        if not it["acked_by"]:
            it["acked_by"] = actor
            it["acked_by_name"] = self.roster.engineers.get(actor, {}).get("name", actor)
            it["acked_at"] = self.sim.iso()
            self.emit("handoff_ack", f"{r['id']}: {it['acked_by_name']} acknowledged “{it['title']}”",
                      severity="success", actor=actor, incident=it["ref"] if str(it["ref"]).startswith("INC") else None)
        if all(i["acked_by"] for i in r["items"]) and not r["complete"]:
            r["complete"] = True
            self.emit("handoff_complete", f"{r['id']} fully acknowledged — nothing lost in handoff",
                      severity="success", actor=actor)
        return r

    # ------------------------------------------------------------ snapshot
    def snapshot(self) -> dict:
        inc = sorted(self.incidents.incidents.values(),
                     key=lambda i: (i.status == "resolved", -i.score, -i.created))
        engineers = []
        for e in self.roster.engineers.values():
            engineers.append({**e, "on_shift": e["shift"] == self._shift_id,
                              "load": self.incidents.load_of(e["id"]),
                              "open_incidents": [i.id for i in self.incidents.open_incidents
                                                 if i.assignee == e["id"] or e["id"] in i.responders]})
        alerts = self.incidents.alerts.values()
        n_inc = sum(1 for i in self.incidents.incidents.values() if not i.title.startswith("[merged"))
        n_alerts = len(self.incidents.alerts)
        return {
            "type": "state",
            "clock": {"time": self.sim.iso(), "now_min": round(self.sim.now, 2), "speed": self.sim.speed,
                      "paused": self.sim.paused, "speeds": SPEEDS, "shift": self.shift_info()},
            "topology_version": self.topo.version,
            "nodes": self.sim.node_snapshot(),
            "incidents": [self.incidents.incident_dict(i) for i in inc[:40]],
            "alerts": [a.to_dict(self) for a in sorted(alerts, key=lambda a: -a.last_seen)[:80]],
            "migrations": self.planner.snapshot(),
            "auto_mode": self.planner.auto_mode,
            "handoffs": self.handoffs[:10],
            "timeline": self.timeline[-300:],
            "engineers": engineers,
            "faults": [f.to_dict(self.sim.now) for f in self.sim.faults.values() if f.preset != "noise"],
            "stats": {"raw_events": self.incidents.raw_events, "alerts": n_alerts,
                      "active_alerts": sum(1 for a in alerts if a.active), "incidents": n_inc,
                      "open_incidents": len([i for i in self.incidents.open_incidents]),
                      "noise_reduction_pct": round(100 * (1 - n_inc / n_alerts)) if n_alerts else 0},
            "llm": self.llm.status(),
        }
