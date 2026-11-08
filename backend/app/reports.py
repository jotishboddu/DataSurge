"""Incident summaries and shift handoff reports (Claude + template fallback)."""
from __future__ import annotations

import itertools
import json
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .engine import Engine

_handoff_ids = itertools.count(1)
_item_ids = itertools.count(1)

PRESET_ROOT_CAUSE = {
    "cooling_failure": "Chiller/CRAC hardware fault (compressor/unit failure) — chilled water lost.",
    "power_feed_loss": "Utility feed loss with generator failing to start; UPS carried load on battery.",
    "tor_flapping": "Flapping ToR uplinks (suspected bad optic) causing packet loss.",
    "storage_degradation": "Multiple OSD disk failures; cluster rebuilding with elevated latency.",
    "gpu_ecc": "GPU memory ECC error storm, progressing toward XID 79 (GPU fell off the bus).",
    "maintenance": "Planned maintenance window.",
    "noise": "Transient, self-clearing condition (likely noise).",
}

SUMMARY_SYSTEM = (
    "You are the incident scribe for an AI data center operations team. Write for an on-call engineer "
    "who was not there. Be concrete: name components, numbers and times from the data. Never invent facts "
    "that are not in the data; say 'unknown' instead. Use exactly these markdown headings, in order: "
    "## What broke, ## Root cause, ## What was done, ## What worked, ## What didn't, ## Current status. "
    "Use short bullet points under each heading. Keep it under 250 words."
)

HANDOFF_SYSTEM = (
    "You write shift handoff notes for an AI data center operations team. The incoming engineers must be "
    "able to act on it in two minutes. Be concrete and use only facts from the data. Use exactly these "
    "markdown headings: ## Situation, ## Open incidents, ## Things to watch, ## Pending migrations, "
    "## Promises to other teams. Short bullets. If a section has nothing, write '- None'. Under 300 words."
)


def _events_for(engine: "Engine", inc_id: str) -> list[dict]:
    return [ev for ev in engine.timeline if ev.get("incident") == inc_id]


def incident_context(engine: "Engine", inc_id: str) -> dict:
    inc = engine.incidents.incidents[inc_id]
    d = engine.incidents.incident_dict(inc)
    faults = [f for f in engine.fault_history if f["target"] == inc.root or f["target"] in engine.topo.ancestors(inc.root)]
    return {
        "incident": {k: d[k] for k in ("id", "title", "root_name", "category", "region", "status", "priority",
                                       "score", "created", "assignee_name", "acked_by_name", "acked_at",
                                       "resolved_at", "esc_level", "merged_from")},
        "sim_time_now": engine.sim.iso(),
        "injected_fault": faults[-1] if faults else None,
        "alerts": [{k: a[k] for k in ("severity", "message", "count", "active", "first_seen")} for a in d["alerts"]][:25],
        "blast_radius": {"statements": d["blast"].get("statements", []),
                         "workloads": d["blast"].get("workloads", []),
                         "customers": d["blast"].get("customers", [])},
        "timeline": [{"t": ev["t"], "kind": ev["kind"], "msg": ev["message"]} for ev in _events_for(engine, inc_id)][-60:],
        "notes": d["notes"],
        "migrations": [{k: m.get(k) for k in ("id", "kind", "workload_name", "to_name", "status", "risk", "approved_by")}
                       for m in engine.planner.migrations.values() if m.get("incident_id") == inc_id],
    }


def template_summary(engine: "Engine", inc_id: str) -> str:
    ctx = incident_context(engine, inc_id)
    inc = ctx["incident"]
    tl = ctx["timeline"]
    kinds = lambda *k: [e for e in tl if e["kind"] in k]
    lines = ["## What broke", f"- {inc['title']}"]
    for s in ctx["blast_radius"]["statements"][:3]:
        lines.append(f"- {s}")
    if ctx["blast_radius"]["workloads"]:
        lines.append("- Workloads affected: " + ", ".join(
            f"{w['name']} ({w['customer']})" for w in ctx["blast_radius"]["workloads"][:6]))
    lines.append(f"- {len(ctx['alerts'])} related alerts grouped into this incident")
    lines.append("## Root cause")
    f = ctx["injected_fault"]
    lines.append(f"- {PRESET_ROOT_CAUSE.get(f['preset'], 'Under investigation.')}" if f else "- Unknown — under investigation.")
    lines.append("## What was done")
    done = kinds("routed", "ack", "repair", "migration_approved", "note", "commitment", "watch", "escalated")
    lines += [f"- {e['t'][11:16]} {e['msg']}" for e in done[-8:]] or ["- No actions recorded yet."]
    lines.append("## What worked")
    worked = kinds("migration_completed", "fault_cleared", "ack", "job_restarted")
    lines += [f"- {e['msg']}" for e in worked[-6:]] or ["- Nothing confirmed yet."]
    lines.append("## What didn't")
    bad = kinds("escalated", "migration_failed", "migration_blocked", "job_crashed", "priority_changed")
    lines += [f"- {e['msg']}" for e in bad[-6:]] or ["- No failed actions recorded."]
    lines.append("## Current status")
    active = sum(1 for a in ctx["alerts"] if a["active"])
    st = inc["status"]
    lines.append(f"- {st.capitalize()} · {inc['priority']} · {active} alert(s) still active"
                 + (f" · resolved {inc['resolved_at'][11:16]}" if inc["resolved_at"] else ""))
    if inc["assignee_name"]:
        lines.append(f"- Owner: {inc['assignee_name']}" + (f" (acked by {inc['acked_by_name']})" if inc["acked_by_name"] else " (not yet acknowledged)"))
    return "\n".join(lines)


async def generate_summary(engine: "Engine", inc_id: str) -> dict:
    tmpl = template_summary(engine, inc_id)
    out = {"text": tmpl, "source": "template", "generated_at": engine.sim.iso(), "pending": engine.llm.available}
    engine.incidents.incidents[inc_id].summary = out
    if not engine.llm.available:
        out["pending"] = False
        return out
    ctx = incident_context(engine, inc_id)
    prompt = "Summarize this incident from the data below.\n\n<incident_data>\n" + json.dumps(ctx, indent=1, default=str) + "\n</incident_data>"
    text = await engine.llm.complete(SUMMARY_SYSTEM, prompt)
    if text:
        out = {"text": text, "source": "claude", "model": engine.llm.model, "generated_at": engine.sim.iso(), "pending": False}
    else:
        out = {**out, "pending": False, "fallback_reason": engine.llm.last_error}
    if inc_id in engine.incidents.incidents:
        engine.incidents.incidents[inc_id].summary = out
    return out


# =============================================================== handoff
def build_handoff(engine: "Engine", from_shift: dict, to_shift: dict, reason: str) -> dict:
    e = engine
    names = e.roster.engineers
    items: list[dict] = []

    def item(kind, title, detail, ref=None):
        items.append({"id": f"H{next(_item_ids)}", "kind": kind, "title": title, "detail": detail,
                      "ref": ref, "acked_by": None, "acked_by_name": None, "acked_at": None})

    for inc in sorted(e.incidents.open_incidents, key=lambda i: -i.score):
        d = e.incidents.incident_dict(inc)
        eta = d["blast"].get("earliest_eta")
        detail = (f"{d['status'].capitalize()}; {d['active_alerts']} active alerts. "
                  f"Owner now {d['assignee_name'] or '—'}"
                  + (f"; acked by {d['acked_by_name']}" if d["acked_by_name"] else "; NOT acknowledged")
                  + (f". Earliest impact ~{eta:.0f} min." if eta else ".")
                  + (f" Repair dispatched." if d["repair_dispatched"] else ""))
        item("incident", f"{d['id']} [{d['priority']}] {d['title']}", detail, d["id"])

    watch_nodes = [(nid, ef) for nid, ef in e.sim.eff.items()
                   if e.topo.nodes[nid]["kind"] not in ("workload",) and (ef.status != "ok" or ef.forecast)
                   and ef.cause == nid]
    for nid, ef in watch_nodes[:6]:
        n = e.topo.nodes[nid]
        fc = f" — forecast {ef.forecast.status} in ~{ef.forecast.eta:.0f} min ({ef.forecast.reason})" if ef.forecast else ""
        item("watch", f"{n['name']} ({n['region']}) is {ef.status}", (ef.reason or "") + fc, nid)
    for inc in e.incidents.incidents.values():
        if inc.status == "resolved" and inc.resolved_at is not None and e.sim.now - inc.resolved_at < 120 \
                and not inc.title.startswith("[merged"):
            item("watch", f"{inc.id} resolved at {e.sim.iso(inc.resolved_at)[11:16]} — watch for recurrence",
                 inc.title, inc.id)
        for n in inc.notes:
            if n["kind"] == "watch":
                item("watch", n["text"], f"Noted by {n['author_name']} on {inc.id} at {n['t'][11:16]}", inc.id)

    for m in e.planner.migrations.values():
        if m["status"] in ("suggested", "in_progress", "approved", "no_target"):
            st = {"suggested": "awaiting approval", "in_progress": f"in progress ({m['progress_pct']}%)",
                  "no_target": "blocked — no capacity"}.get(m["status"], m["status"])
            item("migration", f"{m['id']} {m['workload_name']} → {m.get('to_name', '—')}",
                 f"{st}; risk {m.get('risk', '—')}; {m['customer']} ({m['tier']})", m["id"])

    for inc in e.incidents.incidents.values():
        for n in inc.notes:
            if n["kind"] == "commitment":
                item("commitment", n["text"], f"Promised by {n['author_name']} on {inc.id} at {n['t'][11:16]}", inc.id)

    out_lead = e.roster.lead(from_shift["id"])
    in_lead = e.roster.lead(to_shift["id"])
    report = {
        "id": f"HO-{next(_handoff_ids):03d}", "created": e.sim.iso(), "created_min": e.sim.now,
        "from_shift": from_shift["name"], "to_shift": to_shift["name"], "to_shift_id": to_shift["id"],
        "outgoing_lead": out_lead["name"] if out_lead else None,
        "incoming_lead": in_lead["name"] if in_lead else None, "incoming_lead_id": in_lead["id"] if in_lead else None,
        "reason": reason, "items": items, "narrative": template_handoff(e, items, from_shift, to_shift),
        "narrative_source": "template", "narrative_pending": e.llm.available, "complete": not items,
        "overdue_notified": False,
    }
    return report


def template_handoff(engine: "Engine", items: list[dict], from_shift: dict, to_shift: dict) -> str:
    by = lambda k: [i for i in items if i["kind"] == k]
    inc = by("incident")
    p1 = sum(1 for i in inc if "[P1]" in i["title"])
    lines = ["## Situation",
             f"- {from_shift['name']} → {to_shift['name']} at {engine.sim.iso()[11:16]}. "
             f"{len(inc)} open incident(s){f', {p1} at P1' if p1 else ''}."]
    for head, kind in (("## Open incidents", "incident"), ("## Things to watch", "watch"),
                       ("## Pending migrations", "migration"), ("## Promises to other teams", "commitment")):
        lines.append(head)
        lines += [f"- {i['title']} — {i['detail']}" for i in by(kind)] or ["- None"]
    return "\n".join(lines)


async def generate_handoff_narrative(engine: "Engine", report: dict):
    if not engine.llm.available:
        report["narrative_pending"] = False
        return
    data = {"from_shift": report["from_shift"], "to_shift": report["to_shift"], "time": report["created"],
            "items": [{k: i[k] for k in ("kind", "title", "detail")} for i in report["items"]],
            "recent_timeline": [ev["message"] for ev in engine.timeline[-40:]]}
    prompt = "Write the shift handoff from this data.\n\n<handoff_data>\n" + json.dumps(data, indent=1) + "\n</handoff_data>"
    text = await engine.llm.complete(HANDOFF_SYSTEM, prompt)
    report["narrative_pending"] = False
    if text:
        report["narrative"] = text
        report["narrative_source"] = "claude"
        report["model"] = engine.llm.model
    else:
        report["fallback_reason"] = engine.llm.last_error
