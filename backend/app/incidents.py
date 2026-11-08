"""Alerts, de-duplication, incident grouping, priority scoring, routing and
escalation (missed-warning protection)."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml

from .topology import DATA_DIR, SEV, THERMAL_LIMIT

if TYPE_CHECKING:
    from .engine import Engine

SEVERITY_RANK = {"info": 0, "warn": 1, "crit": 2}
CATEGORY_BY_KIND = {
    "power_feed": "power", "ups": "power", "chiller": "cooling", "crac": "cooling",
    "rack": "cooling", "spine": "network", "leaf": "network", "storage": "storage",
    "gpu_node": "gpu", "workload": "gpu",
}
TIER_POINTS = {"platinum": 10, "gold": 6, "silver": 2}
LOAD_WEIGHT = {"P1": 4, "P2": 3, "P3": 2, "P4": 1}

_alert_ids = itertools.count(1)
_incident_ids = itertools.count(1001)


# ============================================================== alert rules
def evaluate_rules(engine: "Engine") -> list[tuple[str, str, str, str]]:
    """Return firing alerts as (rule, node_id, severity, message)."""
    sim, topo = engine.sim, engine.topo
    out: list[tuple[str, str, str, str]] = []
    for nid, n in topo.nodes.items():
        m = sim.metrics[nid]
        o = sim.own[nid]
        e = sim.eff[nid]
        k = n["kind"]
        name = n["name"]
        if o.maintenance:
            continue
        if k == "power_feed" and o.status == "down":
            out.append(("feed_lost", nid, "crit", f"{name} lost — 0 V, generator failed to start"))
        elif k == "ups":
            if o.status == "down":
                out.append(("ups_down", nid, "crit", f"{name} output lost — battery exhausted"))
            elif m["on_battery"]:
                rt = n.get("runtime_min", 15) * m["battery_pct"] / 100
                out.append(("ups_battery", nid, "crit", f"{name} on battery — {rt:.0f} min runtime left "
                            f"({m['battery_pct']:.0f}%)"))
        elif k == "chiller" and o.status == "down":
            out.append(("chiller_trip", nid, "crit", f"{name} tripped — {o.reason or 'fault'}"))
        elif k == "crac":
            if o.status == "down":
                out.append(("crac_fail", nid, "crit", f"{name} failed"))
            elif e.status == "degraded":
                out.append(("crac_supply", nid, "warn", f"{name} supply air {m['supply_air_c']:.1f}°C — "
                            "chilled water lost"))
        elif k == "rack":
            t = m["inlet_c"]
            if t >= THERMAL_LIMIT:
                out.append(("rack_temp", nid, "crit", f"{name} inlet {t:.1f}°C — above thermal limit"))
            elif t >= 30:
                out.append(("rack_temp", nid, "warn", f"{name} inlet {t:.1f}°C (warn ≥30°C)"))
            if e.forecast and e.forecast.eta <= 30 and o.status == "ok":
                out.append(("rack_predict", nid, "warn",
                            f"{name} predicted to {e.forecast.reason} in "
                            + (f"~{e.forecast.eta:.0f} min" if e.forecast.eta >= 1 else "<1 min")))
        elif k == "gpu_node":
            if o.status == "down":
                out.append(("gpu_down", nid, "crit", f"{name}: {o.reason}"))
            elif m["ecc_rate"] > 30:
                sev = "crit" if m["ecc_rate"] > 150 else "warn"
                out.append(("gpu_ecc", nid, sev, f"{name}: {m['ecc_rate']:.0f} correctable ECC errors/min"))
            if m["temp_c"] >= 85 and o.status != "down":
                out.append(("gpu_temp", nid, "warn", f"{name}: GPU temp {m['temp_c']:.0f}°C — throttling"))
        elif k in ("spine", "leaf"):
            if m["loss_pct"] > 1:
                out.append(("net_loss", nid, "crit", f"{name}: packet loss {m['loss_pct']:.1f}%"))
            if m["flaps"] > 3:
                out.append(("net_flap", nid, "warn", f"{name}: interface flapping ({m['flaps']} flaps)"))
        elif k == "storage":
            if o.status == "down":
                out.append(("stor_ro", nid, "crit", f"{name}: cluster READ-ONLY"))
            elif m["failed_disks"] > 0:
                out.append(("stor_osd", nid, "crit", f"{name}: {m['failed_disks']} OSDs down, rebuild "
                            f"{m['rebuild_pct'] or 0:.0f}%"))
            if m["latency_ms"] > 15:
                out.append(("stor_lat", nid, "warn", f"{name}: client latency {m['latency_ms']:.0f} ms"))
        elif k == "workload":
            if n["wtype"] == "inference":
                if e.status == "down":
                    out.append(("wl_down", nid, "crit", f"{name}: endpoint unavailable"))
                else:
                    if m["p99_ms"] > n.get("latency_budget_ms", 250):
                        out.append(("wl_p99", nid, "crit", f"{name}: p99 {m['p99_ms']:.0f} ms > "
                                    f"{n.get('latency_budget_ms')} ms SLO"))
                    if m["error_pct"] > 1:
                        out.append(("wl_err", nid, "warn", f"{name}: error rate {m['error_pct']:.1f}%"))
            else:
                if m["state"] == "crashed":
                    out.append(("wl_crash", nid, "crit", f"{name}: job crashed, waiting for capacity"))
                elif m["throughput_pct"] < 75 and not n.get("_migrating"):
                    out.append(("wl_slow", nid, "warn", f"{name}: throughput {m['throughput_pct']:.0f}%"))
    for f in sim.faults.values():
        if f.preset == "noise":
            out.append(("noise", f.target, f.params.get("severity", "info"),
                        f"{topo.nodes[f.target]['name']}: {f.label}"))
    return out


# ================================================================== models
@dataclass
class Alert:
    id: str
    key: str
    rule: str
    node: str
    severity: str
    message: str
    first_seen: float
    last_seen: float
    count: int = 1
    active: bool = True
    cleared_at: Optional[float] = None
    incident_id: Optional[str] = None

    def to_dict(self, engine: "Engine"):
        return {
            "id": self.id, "rule": self.rule, "node": self.node, "severity": self.severity,
            "message": self.message, "first_seen": engine.sim.iso(self.first_seen),
            "last_seen": engine.sim.iso(self.last_seen), "count": self.count, "active": self.active,
            "incident_id": self.incident_id, "region": engine.topo.nodes[self.node]["region"],
        }


@dataclass
class Incident:
    id: str
    root: str
    category: str
    region: str
    created: float
    title: str = ""
    status: str = "open"  # open | acknowledged | mitigating | resolved
    alert_ids: list[str] = field(default_factory=list)
    priority: str = "P4"
    score: int = 0
    breakdown: dict = field(default_factory=dict)
    assignee: Optional[str] = None
    backup: Optional[str] = None
    lead: Optional[str] = None
    responders: list[str] = field(default_factory=list)
    esc_level: int = 0
    next_esc_at: Optional[float] = None
    acked_by: Optional[str] = None
    acked_at: Optional[float] = None
    resolved_at: Optional[float] = None
    quiet_since: Optional[float] = None
    notes: list[dict] = field(default_factory=list)
    summary: Optional[dict] = None
    blast: dict = field(default_factory=dict)
    merged_from: list[str] = field(default_factory=list)
    repair_dispatched: bool = False
    title_sev: int = 0


ESC_STEPS = ["Notified primary", "Re-notified primary (page + phone)", "Escalated to backup engineer",
             "Escalated to shift lead"]


class Roster:
    def __init__(self, path: Path = DATA_DIR / "roster.yaml"):
        raw = yaml.safe_load(path.read_text())
        self.shifts = raw["shifts"]
        self.engineers = {e["id"]: e for e in raw["engineers"]}
        self.ack_timeout = raw.get("ack_timeout_min", {"P1": 3, "P2": 8, "P3": 15, "P4": 30})

    @staticmethod
    def _mins(hhmm: str) -> int:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    def shift_at(self, minute_of_day: float) -> dict:
        for s in self.shifts:
            a, b = self._mins(s["start"]), self._mins(s["end"])
            if a < b and a <= minute_of_day < b:
                return s
            if a > b and (minute_of_day >= a or minute_of_day < b):
                return s
        return self.shifts[0]

    def on_shift(self, shift_id: str) -> list[dict]:
        return [e for e in self.engineers.values() if e["shift"] == shift_id]

    def lead(self, shift_id: str) -> Optional[dict]:
        return next((e for e in self.on_shift(shift_id) if e["role"] == "lead"), None)


# ========================================================= incident manager
class IncidentManager:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.alerts: dict[str, Alert] = {}
        self.by_key: dict[str, Alert] = {}
        self.incidents: dict[str, Incident] = {}
        self.raw_events = 0
        self._last_count_min = -1

    # ------------------------------------------------------------- helpers
    @property
    def open_incidents(self) -> list[Incident]:
        return [i for i in self.incidents.values() if i.status != "resolved"]

    def load_of(self, eng_id: str) -> int:
        return sum(LOAD_WEIGHT[i.priority] for i in self.open_incidents if i.assignee == eng_id)

    def incident_for_node(self, nid: str) -> Optional[Incident]:
        eff = self.engine.sim.eff.get(nid)
        cause = eff.cause if eff else None
        for inc in self.open_incidents:
            if inc.root == nid or inc.root == cause:
                return inc
            if nid in {self.alerts[a].node for a in inc.alert_ids}:
                return inc
            if nid in {x["id"] for x in inc.blast.get("affected", [])}:
                return inc
        return None

    # --------------------------------------------------------------- tick
    def tick(self):
        e = self.engine
        now = e.sim.now
        firing = evaluate_rules(e)
        seen_keys = set()
        count_tick = int(now) != self._last_count_min
        self._last_count_min = int(now)
        for rule, nid, sev, msg in firing:
            key = f"{rule}:{nid}"
            seen_keys.add(key)
            if count_tick:
                self.raw_events += 1
            a = self.by_key.get(key)
            if a and a.active:
                if SEVERITY_RANK[sev] > SEVERITY_RANK[a.severity]:
                    e.emit("alert_escalated", f"{msg}", severity=sev, node=nid, incident=a.incident_id)
                a.severity, a.message, a.last_seen = sev, msg, now
                continue
            if a and not a.active and a.cleared_at is not None and now - a.cleared_at < 15:
                # flapping alert: reopen the same alert instead of creating a new one
                a.active, a.cleared_at, a.last_seen, a.severity, a.message = True, None, now, sev, msg
                a.count += 1
                self.raw_events += 1
                inc = self.incidents.get(a.incident_id or "")
                if inc and inc.status == "resolved":
                    self._attach(a)
                e.emit("alert_refired", f"{msg} (re-fired ×{a.count}, de-duplicated)", severity=sev,
                       node=nid, incident=a.incident_id)
                continue
            a = Alert(id=f"A{next(_alert_ids)}", key=key, rule=rule, node=nid, severity=sev,
                      message=msg, first_seen=now, last_seen=now)
            self.raw_events += 1
            self.alerts[a.id] = a
            self.by_key[key] = a
            self._attach(a)
            e.emit("alert", msg, severity=sev, node=nid, incident=a.incident_id)

        for key, a in self.by_key.items():
            if a.active and key not in seen_keys:
                a.active, a.cleared_at = False, now
                e.emit("alert_cleared", f"Cleared: {a.message}", severity="success", node=a.node,
                       incident=a.incident_id)

        for inc in self.open_incidents:
            self._refresh(inc)
            self._escalate(inc)
            self._auto_resolve(inc)

    # ------------------------------------------------------------ grouping
    def _attach(self, a: Alert):
        e = self.engine
        eff = e.sim.eff[a.node]
        cause = eff.cause if (eff.cause and eff.cause in e.topo.nodes) else a.node
        if a.rule == "noise":
            cause = a.node
        ancestors = e.topo.ancestors(a.node)

        # 1) an open incident already rooted at this alert's cause / upstream of it
        impacted = eff.status != "ok" or eff.forecast is not None
        best = None
        for inc in self.open_incidents:
            if inc.root == cause or inc.root == a.node:
                best = inc
                break
            if a.rule != "noise" and impacted and inc.root in ancestors and best is None:
                best = inc
        if best:
            self._add_alert(best, a)
            return

        # 2) new root cause: absorb open incidents that are downstream symptoms of it
        inc = self._create(cause)
        for other in list(self.open_incidents):
            if other.id == inc.id:
                continue
            o_eff = e.sim.eff[other.root]
            if o_eff.cause == cause or (cause in e.topo.ancestors(other.root) and o_eff.status != "ok"):
                self._merge(other, inc)
        self._add_alert(inc, a)

    def _add_alert(self, inc: Incident, a: Alert):
        a.incident_id = inc.id
        if a.id not in inc.alert_ids:
            inc.alert_ids.append(a.id)
        if inc.status == "resolved":
            inc.status = "open"
            inc.resolved_at = None
        inc.quiet_since = None
        if a.node == inc.root and SEVERITY_RANK[a.severity] >= max(1, inc.title_sev):
            inc.title = self._title(inc, a)
            inc.title_sev = SEVERITY_RANK[a.severity]

    def _title(self, inc: Incident, a: Optional[Alert] = None) -> str:
        n = self.engine.topo.nodes[inc.root]
        if a and a.node == inc.root:
            msg = a.message
        else:
            msg = f"{n['name']} — {self.engine.sim.eff[inc.root].reason or 'issue detected'}"
        return f"{msg} · {n['region']}"

    def _create(self, root: str) -> Incident:
        e = self.engine
        n = e.topo.nodes[root]
        inc = Incident(id=f"INC-{next(_incident_ids)}", root=root,
                       category=CATEGORY_BY_KIND.get(n["kind"], "gpu"), region=n["region"],
                       created=e.sim.now)
        inc.title = self._title(inc)
        self.incidents[inc.id] = inc
        self._refresh(inc)
        e.emit("incident_created", f"{inc.id} opened: {inc.title} [{inc.priority}, score {inc.score}]",
               severity="crit" if inc.priority in ("P1", "P2") else "warn", node=root, incident=inc.id)
        self._route(inc)
        return inc

    def _merge(self, src: Incident, dst: Incident):
        e = self.engine
        for aid in src.alert_ids:
            self.alerts[aid].incident_id = dst.id
            if aid not in dst.alert_ids:
                dst.alert_ids.append(aid)
        dst.notes += src.notes
        dst.merged_from.append(src.id)
        if src.acked_by and not dst.acked_by:
            dst.acked_by, dst.acked_at, dst.status = src.acked_by, src.acked_at, "acknowledged"
            dst.next_esc_at = None
        src.status = "resolved"
        src.resolved_at = e.sim.now
        src.title = f"[merged into {dst.id}] {src.title}"
        e.emit("incident_merged", f"{src.id} merged into {dst.id} — common root cause "
               f"{e.topo.nodes[dst.root]['name']}", severity="info", incident=dst.id)

    # ------------------------------------------------------------ priority
    def _refresh(self, inc: Incident):
        e = self.engine
        inc.blast = e.blast_radius([inc.root], mode="live")
        active = [self.alerts[a] for a in inc.alert_ids if self.alerts[a].active]
        sev = max((SEVERITY_RANK[a.severity] for a in active), default=0)
        sev_pts = [8, 22, 40][sev]
        wl = inc.blast.get("workloads", [])
        blast_pts = min(20, round(3 * len(wl) + 0.5 * len(inc.blast.get("affected", []))))
        sla_pts = min(20, sum(TIER_POINTS.get(w["tier"], 2) for w in wl))
        eta = inc.blast.get("earliest_eta")
        impacted_now = any(x["status"] in ("degraded", "down") for x in inc.blast.get("affected", [])) \
            or e.sim.eff[inc.root].status in ("degraded", "down")
        if impacted_now and active:
            tti = 15
        elif eta is None:
            tti = 0
        else:
            tti = 15 if eta <= 5 else 11 if eta <= 15 else 7 if eta <= 30 else 4 if eta <= 60 else 0
        related = min(10, 2 * max(0, len(active) - 1))
        score = min(100, sev_pts + blast_pts + sla_pts + tti + related)
        if not active:
            score = min(score, 25)
        label = "P1" if score >= 70 else "P2" if score >= 50 else "P3" if score >= 30 else "P4"
        old = inc.priority
        inc.score = score
        inc.breakdown = {"severity": sev_pts, "blast_radius": blast_pts, "sla_impact": sla_pts,
                         "time_to_impact": tti, "related_alerts": related}
        if label != old and inc.assignee:
            inc.priority = label
            if int(label[1]) < int(old[1]):
                e.emit("priority_changed", f"{inc.id} priority raised {old} → {label} (score {score})",
                       severity="warn", incident=inc.id)
                if inc.next_esc_at is not None:
                    inc.next_esc_at = min(inc.next_esc_at, e.sim.now + self.engine.roster.ack_timeout[label])
        else:
            inc.priority = label

    # ------------------------------------------------------------- routing
    def _candidates(self, category: str, shift_id: str, exclude: set[str]) -> list[dict]:
        engs = [x for x in self.engine.roster.on_shift(shift_id) if x["role"] != "lead" and x["id"] not in exclude]
        primary = [x for x in engs if x["skills"][0] == category]
        secondary = [x for x in engs if category in x["skills"][1:]]
        key = lambda x: (self.load_of(x["id"]), x["name"])
        return sorted(primary, key=key) + sorted(secondary, key=key)

    def _route(self, inc: Incident, reason: str = "routed"):
        e = self.engine
        shift = e.current_shift()
        cands = self._candidates(inc.category, shift["id"], set())
        lead = e.roster.lead(shift["id"])
        inc.lead = lead["id"] if lead else None
        if cands:
            inc.assignee = cands[0]["id"]
            inc.backup = cands[1]["id"] if len(cands) > 1 else inc.lead
        else:
            inc.assignee, inc.backup = inc.lead, None
        inc.responders = [inc.assignee]
        eng = e.roster.engineers[inc.assignee]
        skill = "primary" if eng["skills"][0] == inc.category else "secondary"
        e.emit("routed", f"{inc.id} {reason} to {eng['name']} ({inc.category} — {skill} skill, load "
               f"{self.load_of(inc.assignee)}); backup "
               f"{e.roster.engineers[inc.backup]['name'] if inc.backup else '—'}",
               severity="info", incident=inc.id, actor="datasurge")
        if inc.status in ("open",):
            inc.esc_level = 0
            inc.next_esc_at = e.sim.now + e.roster.ack_timeout[inc.priority]

    def reroute_for_shift(self):
        for inc in self.open_incidents:
            prev = inc.assignee
            self._route(inc, reason="re-routed at shift change")
            if inc.status != "open":
                inc.next_esc_at = None
            if prev and inc.assignee != prev and inc.status != "open":
                # ownership moved: the new owner must acknowledge too
                inc.status = "open"
                inc.acked_by = None
                inc.esc_level = 0
                inc.next_esc_at = self.engine.sim.now + self.engine.roster.ack_timeout[inc.priority]

    # ---------------------------------------------------------- escalation
    def _escalate(self, inc: Incident):
        e = self.engine
        if inc.status != "open" or inc.next_esc_at is None or e.sim.now < inc.next_esc_at:
            return
        inc.esc_level += 1
        T = e.roster.ack_timeout[inc.priority]
        names = e.roster.engineers
        if inc.esc_level == 1:
            msg = f"{inc.id} not acknowledged in {T} min — re-notifying {names[inc.assignee]['name']} (page + phone)"
            inc.next_esc_at = e.sim.now + T
        elif inc.esc_level == 2 and inc.backup:
            msg = f"{inc.id} still unacknowledged — escalated to backup {names[inc.backup]['name']}"
            if inc.backup not in inc.responders:
                inc.responders.append(inc.backup)
            inc.next_esc_at = e.sim.now + T
        else:
            inc.esc_level = 3
            lead = names.get(inc.lead or "")
            msg = f"{inc.id} still unacknowledged — escalated to shift lead {lead['name'] if lead else '—'}"
            if inc.lead and inc.lead not in inc.responders:
                inc.responders.append(inc.lead)
            inc.next_esc_at = None
        e.emit("escalated", msg, severity="crit", incident=inc.id, actor="datasurge")

    def _auto_resolve(self, inc: Incident):
        e = self.engine
        active = any(self.alerts[a].active for a in inc.alert_ids)
        has_fault = any(f.preset != "noise" for f in e.sim.faults_on(inc.root))
        if active or has_fault:
            inc.quiet_since = None
            return
        if inc.quiet_since is None:
            inc.quiet_since = e.sim.now
            if inc.status != "resolved":
                e.emit("recovering", f"{inc.id}: all alerts clear — monitoring for recurrence",
                       severity="success", incident=inc.id)
        elif e.sim.now - inc.quiet_since >= 8:
            self.resolve(inc.id, actor="datasurge", note="auto-resolved: all alerts clear for 8 min")

    # ------------------------------------------------------------- actions
    def ack(self, inc_id: str, eng_id: str):
        e = self.engine
        inc = self.incidents[inc_id]
        if inc.status != "open":
            return inc
        inc.status = "acknowledged"
        inc.acked_by, inc.acked_at = eng_id, e.sim.now
        inc.next_esc_at = None
        took = e.sim.now - inc.created
        e.emit("ack", f"{inc.id} acknowledged by {e.roster.engineers[eng_id]['name']} "
               f"({took:.1f} min after open)", severity="success", incident=inc.id, actor=eng_id)
        return inc

    def resolve(self, inc_id: str, actor: str, note: str = ""):
        e = self.engine
        inc = self.incidents[inc_id]
        if inc.status == "resolved":
            return inc
        inc.status = "resolved"
        inc.resolved_at = e.sim.now
        inc.next_esc_at = None
        who = e.roster.engineers.get(actor, {}).get("name", actor)
        e.emit("resolved", f"{inc.id} resolved by {who}{' — ' + note if note else ''} "
               f"(duration {e.sim.now - inc.created:.0f} min)", severity="success", incident=inc.id, actor=actor)
        e.request_summary(inc.id)
        return inc

    def add_note(self, inc_id: str, author: str, text: str, kind: str = "note"):
        e = self.engine
        inc = self.incidents[inc_id]
        note = {"t": e.sim.iso(), "author": author, "text": text, "kind": kind,
                "author_name": e.roster.engineers.get(author, {}).get("name", author)}
        inc.notes.append(note)
        label = {"note": "Note", "commitment": "Commitment", "watch": "Watch item"}.get(kind, "Note")
        e.emit(kind if kind != "note" else "note", f"{label} on {inc.id} by {note['author_name']}: {text}",
               severity="info", incident=inc.id, actor=author)
        return inc

    def dispatch_repair(self, inc_id: str, actor: str):
        e = self.engine
        inc = self.incidents[inc_id]
        faults = [f for f in e.sim.faults_on(inc.root) if f.preset != "noise"]
        from .simulation import REPAIR_MIN
        if not faults:
            # also look one level up in case the incident was rooted at a symptom
            for nid in e.topo.ancestors(inc.root):
                faults += [f for f in e.sim.faults_on(nid) if f.preset != "noise"]
        for f in faults:
            if f.repair_at is None:
                f.repair_at = e.sim.now + REPAIR_MIN.get(f.preset, 5)
        inc.repair_dispatched = True
        if inc.status in ("open", "acknowledged"):
            if inc.status == "open":
                self.ack(inc_id, actor)
            inc.status = "mitigating"
        eta = max((f.repair_at - e.sim.now for f in faults), default=0)
        e.emit("repair", f"{e.roster.engineers.get(actor, {}).get('name', actor)} dispatched repair for "
               f"{e.topo.nodes[inc.root]['name']} — ETA {eta:.0f} min", severity="info",
               incident=inc.id, actor=actor)
        return inc

    # ----------------------------------------------------------- snapshot
    def incident_dict(self, inc: Incident) -> dict:
        e = self.engine
        names = e.roster.engineers
        alerts = [self.alerts[a] for a in inc.alert_ids]
        T = e.roster.ack_timeout[inc.priority]
        return {
            "id": inc.id, "title": inc.title, "root": inc.root,
            "root_name": e.topo.nodes[inc.root]["name"], "category": inc.category, "region": inc.region,
            "status": inc.status, "priority": inc.priority, "score": inc.score, "breakdown": inc.breakdown,
            "created": e.sim.iso(inc.created), "age_min": round(e.sim.now - inc.created, 1),
            "assignee": inc.assignee, "assignee_name": names.get(inc.assignee or "", {}).get("name"),
            "backup": inc.backup, "backup_name": names.get(inc.backup or "", {}).get("name"),
            "lead": inc.lead, "responders": inc.responders,
            "esc_level": inc.esc_level, "esc_step": ESC_STEPS[min(inc.esc_level, 3)],
            "next_esc_in": round(inc.next_esc_at - e.sim.now, 2) if inc.next_esc_at is not None else None,
            "ack_timeout_min": T,
            "acked_by": inc.acked_by, "acked_by_name": names.get(inc.acked_by or "", {}).get("name"),
            "acked_at": e.sim.iso(inc.acked_at) if inc.acked_at is not None else None,
            "resolved_at": e.sim.iso(inc.resolved_at) if inc.resolved_at is not None else None,
            "alerts": [a.to_dict(e) for a in alerts],
            "alert_count": len(alerts), "active_alerts": sum(1 for a in alerts if a.active),
            "raw_count": sum(a.count for a in alerts),
            "notes": inc.notes, "summary": inc.summary, "blast": inc.blast,
            "merged_from": inc.merged_from, "repair_dispatched": inc.repair_dispatched,
            "runbook": e.runbooks.get(inc.category),
        }
