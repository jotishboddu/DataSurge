"""Scenario tests for the simulation engine. Run: .venv/bin/python -m pytest tests  (or plain python)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine import Engine  # noqa: E402


def fresh():
    e = Engine()
    e.sim.noise_enabled = False
    return e


def test_baseline_healthy():
    e = fresh()
    e.step(2)
    assert not e.incidents.incidents
    assert all(x.status == "ok" and x.forecast is None for x in e.sim.eff.values())


def test_cooling_failure_groups_into_one_p1_with_thermal_eta():
    e = fresh()
    e.inject("cooling_failure", "use-chiller-1")
    e.step(6)
    open_ = [i for i in e.incidents.open_incidents]
    assert len(open_) == 1
    inc = open_[0]
    assert inc.root == "use-chiller-1" and inc.priority == "P1"
    assert len(inc.alert_ids) >= 5
    assert any("thermal limit" in s for s in inc.blast["statements"])
    assert inc.assignee in ("sofia", "priya", "marcus")


def test_escalation_ladder_without_ack():
    e = fresh()
    e.inject("tor_flapping", "euw-leaf-a")
    e.step(12)
    inc = e.incidents.open_incidents[0]
    assert inc.esc_level == 3


def test_ack_stops_escalation():
    e = fresh()
    e.inject("tor_flapping", "euw-leaf-a")
    e.step(1)
    inc = e.incidents.open_incidents[0]
    e.incidents.ack(inc.id, "dev")
    e.step(10)
    assert inc.esc_level == 0 and inc.status == "acknowledged"


def test_same_region_migration_respects_residency_and_completes():
    e = fresh()
    e.inject("tor_flapping", "euw-leaf-a")
    e.step(2)
    m = next(m for m in e.planner.migrations.values() if m["workload"] == "euw-inf-chat")
    assert m["to_region"] == "eu-west" and m["risk"] == "low"
    e.planner.approve(m["id"], "dev")
    e.step(10)
    assert m["status"] == "completed"
    assert e.topo.nodes["euw-inf-chat"]["host"] == m["to"]


def test_whatif_redundancy():
    e = fresh()
    b = e.blast_radius(["use-spine-1"], "hypothetical")
    assert all(a["status"] in ("at_risk", "ok") for a in b["affected"])  # spine-2 still carries traffic


def test_shift_change_creates_handoff_and_template_summary():
    e = fresh()
    e.inject("gpu_ecc", "usc-gpu-c2")
    e.step(35)  # crosses 06:00
    assert e.handoffs and e.handoffs[0]["items"]
    from app.reports import template_summary
    inc = next(iter(e.incidents.incidents.values()))
    text = template_summary(e, inc.id)
    assert "## What broke" in text and "## Current status" in text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
