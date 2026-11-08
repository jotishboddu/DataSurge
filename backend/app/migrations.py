"""Smart workload and data handoff.

When a workload's host or storage is degraded or forecast to fail, the
planner suggests where to move it: a healthy GPU node with enough free GPUs
of an acceptable type, an allowed region (data residency) and an
acceptable latency, preferring the same region. Each suggestion carries
its reasoning (capacity, cost, risk, time to migrate) and alternatives.

Approved migrations run as timed phases: training jobs checkpoint ->
transfer -> restore; inference endpoints provision -> drain traffic ->
release. Every step is logged to the timeline.
"""
from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Optional

from .topology import SEV

if TYPE_CHECKING:
    from .engine import Engine

_mig_ids = itertools.count(101)
ACTIVE = ("approved", "in_progress")
PENDING = ("suggested",)


class MigrationPlanner:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.migrations: dict[str, dict] = {}
        self.auto_mode = False
        self.cooldown: dict[str, float] = {}

    # ------------------------------------------------------------ helpers
    def _for_workload(self, wid: str, statuses) -> list[dict]:
        return [m for m in self.migrations.values() if m["workload"] == wid and m["status"] in statuses]

    def reserved(self, gpu_id: str) -> int:
        return sum(m["gpus"] for m in self.migrations.values()
                   if m["kind"] == "workload" and m["to"] == gpu_id and m["status"] in PENDING + ACTIVE)

    def _threat(self, nid: str) -> Optional[dict]:
        """Is this host/storage a reason to move? Returns status, eta, reason."""
        e = self.engine.sim.eff[nid]
        if SEV[e.status] >= SEV["degraded"]:
            return {"status": e.status, "eta": 0.0, "reason": e.reason or e.status}
        if e.forecast and e.forecast.eta <= 60:
            return {"status": e.forecast.status, "eta": e.forecast.eta, "reason": e.forecast.reason}
        return None

    def _healthy(self, nid: str) -> bool:
        e = self.engine.sim.eff[nid]
        return e.status == "ok" and e.forecast is None

    # --------------------------------------------------------------- tick
    def tick(self):
        e = self.engine
        topo = e.topo
        for wid, w in topo.nodes.items():
            if w["kind"] != "workload" or w.get("_migrating"):
                continue
            host_threat = self._threat(w["host"])
            stor_threat = self._threat(w["storage"]) if w.get("storage") else None
            pending = self._for_workload(wid, PENDING + ("no_target",))
            if not host_threat and not stor_threat:
                for m in pending:
                    m["status"] = "expired"
                    e.emit("migration_expired", f"{m['id']} for {w['name']} no longer needed — "
                           "source recovered", severity="info", node=wid)
                continue
            if pending or self._for_workload(wid, ACTIVE):
                for m in pending:
                    t = host_threat or stor_threat
                    m["impact_eta"] = round(t["eta"], 1)
                continue
            if e.sim.now < self.cooldown.get(wid, -1):
                continue
            if host_threat:
                self._suggest_workload_move(w, host_threat)
            else:
                self._suggest_data_move(w, stor_threat)

        if self.auto_mode:
            for m in list(self.migrations.values()):
                if m["status"] == "suggested" and m["risk"] == "low":
                    self.approve(m["id"], actor="autopilot")

        for m in self.migrations.values():
            if m["status"] in ACTIVE:
                self._progress(m)

    # ----------------------------------------------------------- planning
    def _base(self, w: dict, threat: dict, kind: str) -> dict:
        e = self.engine
        c = e.topo.customers.get(w["customer"], {})
        inc = e.incidents.incident_for_node(w["host"] if kind != "data" else w["storage"])
        return {
            "id": f"MIG-{next(_mig_ids)}", "kind": kind, "workload": w["id"], "workload_name": w["name"],
            "wtype": w["wtype"], "customer": c.get("name", w["customer"]), "tier": c.get("tier", "silver"),
            "gpus": w["gpus"], "status": "suggested", "created": e.sim.iso(), "created_min": e.sim.now,
            "impact_eta": round(threat["eta"], 1), "threat": threat["reason"],
            "incident_id": inc.id if inc else None, "approved_by": None, "phases": [],
            "phase_idx": 0, "phase_started": None, "progress_pct": 0, "alternatives": [],
        }

    def _score_target(self, w: dict, g: dict, eta: float) -> dict:
        e = self.engine
        topo = e.topo
        cur = topo.nodes[w["host"]]
        same = g["region"] == w["region"]
        lat_add = topo.region_latency(w["home_region"], g["region"])
        free = g["gpus_total"] - topo.gpu_used(g["id"]) - self.reserved(g["id"])
        if w["wtype"] == "training":
            gb = w.get("checkpoint_gb", 500)
            ckpt = max(1.0, gb / 600)
            transfer = 0.0 if same else gb / 120
            phases = [("checkpoint", ckpt), ("transfer", transfer), ("restore", 2.0)]
            data_gb = gb
        else:
            gb = w.get("model_gb", 50)
            prov = 2.0 + gb / 200 + (0 if same else gb / 100)
            phases = [("provision", prov), ("drain", 3.0), ("release", 0.5)]
            data_gb = gb
        phases = [p for p in phases if p[1] > 0]
        time_min = sum(d for _, d in phases)
        cost_delta = w["gpus"] * (g.get("cost_per_gpu_hr", 2) - cur.get("cost_per_gpu_hr", 2))
        egress = 0.0 if same else data_gb * topo.egress_cost_per_gb
        risk_pts, risk_reasons = 0, []
        if not same:
            risk_pts += 1
            risk_reasons.append(f"cross-region move (+{lat_add} ms, {data_gb} GB egress)")
        if eta > 0 and time_min > eta * 0.8:
            risk_pts += 2
            risk_reasons.append(f"~{time_min:.0f} min to migrate vs impact in ~{eta:.0f} min")
        if free - w["gpus"] < 4:
            risk_pts += 1
            risk_reasons.append(f"leaves only {free - w['gpus']} GPUs headroom on {g['name'].split(' ·')[0]}")
        if w["wtype"] == "inference":
            budget = w.get("latency_budget_ms", 250)
            projected = w.get("base_p99_ms", 150) + lat_add
            if projected > 0.85 * budget:
                risk_pts += 1
                risk_reasons.append(f"projected p99 {projected} ms is near the {budget} ms SLO")
        if not risk_reasons:
            risk_reasons.append("target healthy and outside the blast radius")
        risk = "low" if risk_pts == 0 else "medium" if risk_pts <= 2 else "high"
        score = 100 - (0 if same else 25) - time_min * 1.5 - risk_pts * 12 - max(0.0, cost_delta) * 0.5
        return {
            "to": g["id"], "to_name": g["name"], "to_region": g["region"], "same_region": same,
            "free": free, "latency_add_ms": lat_add, "time_min": round(time_min, 1),
            "phases_plan": phases, "cost_delta_hr": round(cost_delta, 2), "egress_usd": round(egress, 2),
            "risk": risk, "risk_reasons": risk_reasons, "score": round(score, 1), "gpu_type": g["gpu_type"],
        }

    def _suggest_workload_move(self, w: dict, threat: dict):
        e = self.engine
        topo = e.topo
        cands, rejected = [], []
        residency = w.get("residency")
        for g in topo.nodes.values():
            if g["kind"] != "gpu_node" or g["id"] == w["host"]:
                continue
            if g["gpu_type"] not in w["gpu_types"]:
                continue
            if residency and g["region"] not in residency:
                continue
            if not self._healthy(g["id"]):
                continue
            free = g["gpus_total"] - topo.gpu_used(g["id"]) - self.reserved(g["id"])
            if free < w["gpus"]:
                rejected.append((g, free))
                continue
            if w["wtype"] == "inference":
                lat = topo.region_latency(w["home_region"], g["region"])
                if w.get("base_p99_ms", 150) + lat > w.get("latency_budget_ms", 250):
                    continue
            cands.append(self._score_target(w, g, threat["eta"]))
        cands.sort(key=lambda c: -c["score"])

        if not cands:
            if w["wtype"] == "training":
                self._suggest_checkpoint(w, threat, rejected)
            elif not self._for_workload(w["id"], ("no_target",)):
                m = self._base(w, threat, "workload")
                m.update(status="no_target", risk="high", to=None, to_name="—", reasons=[
                    f"No healthy node with {w['gpus']}× {'/'.join(w['gpu_types'])} free"
                    + (f" in {', '.join(residency)} (data residency)" if residency else ""),
                    "Consider shedding lower-tier load or scaling down replicas"])
                self.migrations[m["id"]] = m
                e.emit("migration_blocked", f"{m['id']}: no capacity to move {w['name']}", severity="warn",
                       node=w["id"], incident=m["incident_id"])
            return

        best = cands[0]
        m = self._base(w, threat, "workload")
        cur = topo.nodes[w["host"]]
        self._fill(m, w, cur, best)
        m["alternatives"] = [{k: c[k] for k in ("to", "to_name", "to_region", "same_region", "score", "risk",
                                                 "time_min", "cost_delta_hr", "latency_add_ms")}
                             for c in cands[1:4]]
        self.migrations[m["id"]] = m
        e.emit("migration_suggested", f"{m['id']} suggested: move {w['name']} {cur['name'].split(' ·')[0]} → "
               f"{best['to_name'].split(' ·')[0]} ({best['to_region']}) — risk {best['risk']}, "
               f"~{best['time_min']:.0f} min", severity="info", node=w["id"], incident=m["incident_id"],
               actor="datasurge")

    def _fill(self, m: dict, w: dict, cur: dict, c: dict):
        lbl = {"checkpoint": "Checkpoint", "transfer": "Transfer checkpoint", "restore": "Restore & resume",
               "provision": "Provision replicas", "drain": "Drain traffic", "release": "Release old replicas",
               "snapshot": "Snapshot dataset", "sync": "Sync data", "cutover": "Cut over mounts"}
        m.update({
            "from": cur["id"], "from_name": cur["name"], "to": c["to"], "to_name": c["to_name"],
            "to_region": c["to_region"], "same_region": c["same_region"], "risk": c["risk"],
            "risk_reasons": c["risk_reasons"], "time_min": c["time_min"], "cost_delta_hr": c["cost_delta_hr"],
            "egress_usd": c["egress_usd"], "latency_add_ms": c["latency_add_ms"], "score": c["score"],
            "phases": [{"name": n, "label": lbl[n], "dur": round(d, 1), "done": False} for n, d in c["phases_plan"]],
        })
        if m["kind"] == "workload":
            m["reasons"] = [
                f"Capacity: {c['to_name'].split(' ·')[0]} has {c['free']} {c['gpu_type']} free (needs {w['gpus']})",
                f"Hardware: {c['gpu_type']} meets requirement ({'/'.join(w['gpu_types'])})",
                ("Latency: same region (+0 ms)" if c["same_region"] else
                 f"Latency: +{c['latency_add_ms']} ms to {c['to_region']}"
                 + (f" — p99 ≈ {w.get('base_p99_ms', 0) + c['latency_add_ms']} ms vs {w.get('latency_budget_ms')} ms SLO"
                    if w["wtype"] == "inference" else "")),
                f"Cost: {'+' if c['cost_delta_hr'] >= 0 else '−'}${abs(c['cost_delta_hr']):.2f}/hr"
                + (f", one-time egress ${c['egress_usd']:.0f}" if c["egress_usd"] else ""),
                f"Risk: {c['risk']} — {'; '.join(c['risk_reasons'])}",
                f"Time: ~{c['time_min']:.0f} min ("
                + ", ".join(f"{p[0]} {p[1]:.0f}m" for p in c["phases_plan"]) + ")"
                + (f" vs impact in ~{m['impact_eta']:.0f} min" if m["impact_eta"] > 0 else " — already impacted"),
            ]

    def _suggest_checkpoint(self, w: dict, threat: dict, rejected: list):
        e = self.engine
        m = self._base(w, threat, "checkpoint")
        gb = w.get("checkpoint_gb", 500)
        dur = max(1.0, gb / 600)
        last = e.sim.metrics[w["id"]]["last_ckpt"]
        biggest = max(rejected, key=lambda r: r[1], default=None)
        m.update({
            "from": w["host"], "from_name": e.topo.nodes[w["host"]]["name"], "to": w["host"],
            "to_name": "checkpoint in place", "to_region": w["region"], "same_region": True, "risk": "low",
            "risk_reasons": ["no data movement; job keeps running"], "time_min": round(dur, 1),
            "cost_delta_hr": 0.0, "egress_usd": 0.0, "latency_add_ms": 0, "score": 50,
            "phases": [{"name": "checkpoint", "label": "Checkpoint now", "dur": round(dur, 1), "done": False}],
            "reasons": [
                f"No healthy node has {w['gpus']}× {'/'.join(w['gpu_types'])} free"
                + (f" (largest: {biggest[0]['name'].split(' ·')[0]} with {biggest[1]})" if biggest else ""),
                f"Last checkpoint {e.sim.now - last:.0f} min ago — a crash now loses that progress",
                f"Checkpoint now ({gb} GB, ~{dur:.0f} min) caps the loss at ~0 min",
                "Then re-evaluate placement as capacity frees up",
            ],
        })
        self.migrations[m["id"]] = m
        e.emit("migration_suggested", f"{m['id']} suggested: checkpoint {w['name']} now (no capacity to move)",
               severity="info", node=w["id"], incident=m["incident_id"], actor="datasurge")

    def _suggest_data_move(self, w: dict, threat: dict):
        e = self.engine
        topo = e.topo
        residency = w.get("residency")
        cands = []
        for s in topo.nodes.values():
            if s["kind"] != "storage" or s["id"] == w["storage"] or not self._healthy(s["id"]):
                continue
            if residency and s["region"] not in residency:
                continue
            same = s["region"] == w["region"]
            gb = w.get("checkpoint_gb", w.get("model_gb", 100)) * 2
            sync = gb / 400 if same else gb / 120
            phases = [("snapshot", 1.0), ("sync", sync), ("cutover", 0.5)]
            risk_reasons = [] if same else [f"cross-region data path (+{topo.region_latency(w['region'], s['region'])} ms)"]
            if threat["eta"] > 0 and sum(p[1] for p in phases) > threat["eta"] * 0.8:
                risk_reasons.append("sync may not finish before impact")
            risk = "low" if not risk_reasons else "medium" if len(risk_reasons) == 1 else "high"
            cands.append({
                "to": s["id"], "to_name": s["name"], "to_region": s["region"], "same_region": same,
                "free": 0, "latency_add_ms": 0 if same else topo.region_latency(w["region"], s["region"]),
                "time_min": round(sum(p[1] for p in phases), 1), "phases_plan": phases, "cost_delta_hr": 0.0,
                "egress_usd": 0.0 if same else round(gb * topo.egress_cost_per_gb, 2), "risk": risk,
                "risk_reasons": risk_reasons or ["replica healthy, same region"], "gb": gb,
                "score": 100 - (0 if same else 25) - sum(p[1] for p in phases), "gpu_type": "",
            })
        if not cands:
            return
        cands.sort(key=lambda c: -c["score"])
        best = cands[0]
        m = self._base(w, threat, "data")
        cur = topo.nodes[w["storage"]]
        self._fill(m, w, cur, best)
        m["reasons"] = [
            f"Source: {cur['name']} — {threat['reason']}",
            f"Target: {best['to_name']} ({best['to_region']}) is healthy",
            f"Data: ~{best['gb']} GB dataset/checkpoints",
            ("Latency: same region" if best["same_region"] else f"Latency: +{best['latency_add_ms']} ms"),
            f"Risk: {best['risk']} — {'; '.join(best['risk_reasons'])}",
            f"Time: ~{best['time_min']:.0f} min"
            + (f" vs impact in ~{m['impact_eta']:.0f} min" if m["impact_eta"] > 0 else ""),
        ]
        m["alternatives"] = [{k: c[k] for k in ("to", "to_name", "to_region", "same_region", "score", "risk",
                                                 "time_min", "cost_delta_hr", "latency_add_ms")} for c in cands[1:3]]
        self.migrations[m["id"]] = m
        e.emit("migration_suggested", f"{m['id']} suggested: move {w['name']} data {cur['name']} → "
               f"{best['to_name']} — risk {best['risk']}", severity="info", node=w["id"],
               incident=m["incident_id"], actor="datasurge")

    # ---------------------------------------------------------- execution
    def approve(self, mid: str, actor: str, target: Optional[str] = None) -> dict:
        e = self.engine
        m = self.migrations[mid]
        if m["status"] != "suggested":
            return m
        w = e.topo.nodes[m["workload"]]
        if target and target != m["to"] and m["kind"] == "workload":
            g = e.topo.nodes[target]
            c = self._score_target(w, g, m["impact_eta"])
            self._fill(m, w, e.topo.nodes[w["host"]], c)
        if m["kind"] == "workload":
            free = e.topo.nodes[m["to"]]["gpus_total"] - e.topo.gpu_used(m["to"]) - self.reserved(m["to"]) + m["gpus"]
            if free < m["gpus"] or not self._healthy(m["to"]):
                m["status"] = "failed"
                e.emit("migration_failed", f"{mid} cannot start: target no longer has capacity/health — re-planning",
                       severity="warn", node=w["id"], incident=m["incident_id"])
                return m
        m["status"] = "in_progress"
        m["approved_by"] = actor
        m["approved_at"] = e.sim.iso()
        m["auto"] = actor == "autopilot"
        m["phase_idx"] = 0
        m["phase_started"] = e.sim.now
        if m["kind"] in ("workload", "checkpoint"):
            w["_migrating"] = m["kind"] == "workload"
            if w["wtype"] == "training" and m["kind"] == "workload":
                e.sim.metrics[w["id"]]["state"] = "migrating"
        who = "datasurge autopilot (low-risk auto-mode)" if actor == "autopilot" else \
            e.roster.engineers.get(actor, {}).get("name", actor)
        e.emit("migration_approved", f"{mid} approved by {who}: {w['name']} → {m['to_name']}",
               severity="info", node=w["id"], incident=m["incident_id"], actor=actor)
        self._log_phase_start(m)
        return m

    def reject(self, mid: str, actor: str) -> dict:
        e = self.engine
        m = self.migrations[mid]
        if m["status"] not in ("suggested", "no_target"):
            return m
        m["status"] = "rejected"
        self.cooldown[m["workload"]] = e.sim.now + 30
        e.emit("migration_rejected", f"{mid} rejected by {e.roster.engineers.get(actor, {}).get('name', actor)} "
               "— will not re-suggest for 30 min", severity="info", node=m["workload"], incident=m["incident_id"],
               actor=actor)
        return m

    def _log_phase_start(self, m: dict):
        e = self.engine
        p = m["phases"][m["phase_idx"]]
        w = e.topo.nodes[m["workload"]]
        detail = {
            "checkpoint": f"saving step {e.sim.metrics[w['id']].get('step', 0):,} "
                          f"({w.get('checkpoint_gb', 0)} GB) to {e.topo.nodes[w['storage']]['name']}",
            "transfer": f"copying checkpoint to {m['to_region']}",
            "restore": f"restoring on {m['to_name']}",
            "provision": f"starting {w['gpus']} replicas on {m['to_name']}",
            "drain": "shifting traffic 0% → 100% to new replicas",
            "release": f"releasing replicas on {m.get('from_name', '')}",
            "snapshot": "snapshotting dataset", "sync": f"syncing to {m['to_name']}",
            "cutover": "switching mounts to new cluster",
        }.get(p["name"], "")
        e.emit("migration_step", f"{m['id']} · {p['label']} — {detail}", severity="info", node=w["id"],
               incident=m["incident_id"], actor="datasurge")

    def _progress(self, m: dict):
        e = self.engine
        now = e.sim.now
        w = e.topo.nodes[m["workload"]]
        total = sum(p["dur"] for p in m["phases"]) or 1
        p = m["phases"][m["phase_idx"]]
        elapsed = now - m["phase_started"]
        done_before = sum(x["dur"] for x in m["phases"][:m["phase_idx"]])
        m["progress_pct"] = round(min(100, 100 * (done_before + min(elapsed, p["dur"])) / total))
        if p["name"] == "drain":
            e.sim.metrics[w["id"]]["traffic_pct"] = max(0.0, 100 - 100 * min(1.0, elapsed / p["dur"]))
        if elapsed < p["dur"]:
            return
        p["done"] = True
        if p["name"] == "checkpoint":
            mm = e.sim.metrics[w["id"]]
            if e.sim.eff[w["host"]].status == "down":
                e.emit("migration_step", f"{m['id']} · checkpoint failed (host down) — falling back to checkpoint "
                       f"from {now - mm['last_ckpt']:.0f} min ago", severity="warn", node=w["id"],
                       incident=m["incident_id"])
            else:
                mm["last_ckpt"] = now
                e.emit("migration_step", f"{m['id']} · checkpoint saved (step {mm.get('step', 0):,})",
                       severity="success", node=w["id"], incident=m["incident_id"])
        m["phase_idx"] += 1
        m["phase_started"] = now
        if m["phase_idx"] < len(m["phases"]):
            self._log_phase_start(m)
            return
        self._complete(m)

    def _complete(self, m: dict):
        e = self.engine
        topo = e.topo
        w = topo.nodes[m["workload"]]
        m["status"] = "completed"
        m["progress_pct"] = 100
        m["completed_at"] = e.sim.iso()
        if m["kind"] == "workload":
            old = w["host"]
            w["host"] = m["to"]
            new_region = topo.nodes[m["to"]]["region"]
            if new_region != w["region"]:
                w["region"] = new_region
                stores = [s for s in topo.nodes.values() if s["kind"] == "storage" and s["region"] == new_region]
                if stores:
                    w["storage"] = stores[0]["id"]
            w["_latency_add_ms"] = topo.region_latency(w["home_region"], w["region"]) if w["wtype"] == "inference" else 0
            w["_migrating"] = False
            mm = e.sim.metrics[w["id"]]
            if w["wtype"] == "training":
                mm["state"] = "running"
            else:
                mm["traffic_pct"] = 100.0
            topo.bump()
            e.emit("migration_completed", f"{m['id']} completed: {w['name']} now running on {m['to_name']} "
                   f"({w['region']}); moved off {topo.nodes[old]['name']}", severity="success", node=w["id"],
                   incident=m["incident_id"], actor="datasurge")
        elif m["kind"] == "data":
            w["storage"] = m["to"]
            topo.bump()
            e.emit("migration_completed", f"{m['id']} completed: {w['name']} data now served from {m['to_name']}",
                   severity="success", node=w["id"], incident=m["incident_id"], actor="datasurge")
        else:
            e.emit("migration_completed", f"{m['id']} completed: {w['name']} checkpointed — progress protected",
                   severity="success", node=w["id"], incident=m["incident_id"], actor="datasurge")
            self.cooldown[w["id"]] = e.sim.now + 20

    def snapshot(self) -> list[dict]:
        items = sorted(self.migrations.values(), key=lambda m: -m["created_min"])
        return [{k: v for k, v in m.items()} for m in items[:60]]
