"""app.py - The DataSurge website (what the night-shift worker sees)."""
import streamlit as st

import ai

st.set_page_config(page_title="DataSurge", page_icon="⚡", layout="wide")

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}
ICONS = {"critical": "🔴", "warning": "🟡", "info": "🟢"}
# Rough demo numbers for "what it costs per hour if this turns into an outage".
# Swap for real numbers if the CBRE / NMC2 booths give you some.
COST_PER_HOUR = {"critical": 180_000, "warning": 25_000, "info": 0}

# ---- Fake warnings (used until Jotish's data.py is ready) ----
FAKE_WARNINGS = [
    {"id": 1, "location": "Hall B, Rack 12", "type": "temperature",
     "message": "Rack temperature rising", "value": 31.5,
     "level": "critical", "time": "02:14 AM", "status": "open"},
    {"id": 2, "location": "Hall A, Cooling Unit 2", "type": "cooling",
     "message": "Cooling pump vibration slightly high", "value": 4.2,
     "level": "warning", "time": "01:58 AM", "status": "open"},
    {"id": 3, "location": "Hall C, Water Loop", "type": "water",
     "message": "Water flow dropped 5% in the last hour", "value": 95,
     "level": "warning", "time": "01:41 AM", "status": "open"},
    {"id": 4, "location": "Hall C, UPS B", "type": "power",
     "message": "Backup battery at 92%", "value": 92,
     "level": "info", "time": "01:30 AM", "status": "open"},
    {"id": 5, "location": "Hall A, Rack 03", "type": "temperature",
     "message": "Temperature spike cleared on its own", "value": 27.0,
     "level": "info", "time": "12:52 AM", "status": "open"},
]


def load_warnings():
    """Use Jotish's engine if it exists, otherwise the fake list."""
    try:
        from data import get_warnings          # Jotish: data.py -> get_warnings()
        warnings, source = get_warnings(), "live (data.py)"
    except Exception:
        warnings, source = [dict(w) for w in FAKE_WARNINGS], "demo data"
    try:
        from brain import rank                 # Jotish: brain.py -> rank(warnings)
        warnings = rank(warnings)
    except Exception:
        warnings = sorted(warnings, key=lambda w: LEVEL_ORDER.get(w["level"], 9))
    return warnings, source


# ---- Remember what the worker did (acknowledged / resolved) ----
if "status" not in st.session_state:
    st.session_state.status = {}
if "explanations" not in st.session_state:
    st.session_state.explanations = {}

warnings, source = load_warnings()
for w in warnings:
    w["status"] = st.session_state.status.get(w["id"], w.get("status", "open"))

open_ws = [w for w in warnings if w["status"] != "resolved"]


def explain_button(w, key_prefix):
    if st.button("🤖 Explain", key=f"{key_prefix}-explain-{w['id']}"):
        with st.spinner("DataSurge is thinking..."):
            st.session_state.explanations[w["id"]] = ai.explain_warning(w)
    if w["id"] in st.session_state.explanations:
        st.info(st.session_state.explanations[w["id"]])


def action_buttons(w, key_prefix):
    c1, c2 = st.columns(2)
    if w["status"] == "open" and c1.button("👀 I'm on it", key=f"{key_prefix}-ack-{w['id']}"):
        st.session_state.status[w["id"]] = "acknowledged"
        st.rerun()
    if c2.button("✅ Resolved", key=f"{key_prefix}-done-{w['id']}"):
        st.session_state.status[w["id"]] = "resolved"
        st.rerun()


# ---- Header ----
st.title("⚡ DataSurge")
st.caption(f"Your AI teammate for the night shift · source: {source}")

# ---- Numbers at a glance ----
m1, m2, m3, m4 = st.columns(4)
m1.metric("🔴 Critical", sum(w["level"] == "critical" for w in open_ws))
m2.metric("🟡 Warnings", sum(w["level"] == "warning" for w in open_ws))
m3.metric("🟢 Info", sum(w["level"] == "info" for w in open_ws))
m4.metric("💸 At risk (est. / hour)",
          f"${sum(COST_PER_HOUR.get(w['level'], 0) for w in open_ws):,}")

tab_now, tab_handoff = st.tabs(["🚨 Right now", "🔁 Shift handoff"])

with tab_now:
    if not open_ws:
        st.success("🎉 All clear. Nothing needs you right now.")
    else:
        # 1. The ONE thing that needs you
        top = open_ws[0]
        st.error(f"### 🚨 Needs you now\n**{top['message']}** — {top['location']}  \n"
                 f"Reading: {top['value']} · {top['time']} · status: {top['status']}")
        explain_button(top, "top")
        action_buttons(top, "top")

        # 2. Small issues that could grow (so they don't get forgotten)
        small = [w for w in open_ws[1:] if w["level"] == "warning"]
        if small:
            st.subheader("👁️ Don't forget: small issues that could grow")
            for w in small:
                with st.expander(f"{ICONS[w['level']]} {w['location']} — {w['message']}"):
                    st.write(f"Reading: {w['value']} · {w['time']} · status: {w['status']}")
                    explain_button(w, "small")
                    action_buttons(w, "small")

        # 3. Everything else
        rest = [w for w in open_ws[1:] if w["level"] != "warning"]
        if rest:
            st.subheader("Everything else")
            for w in rest:
                st.write(f"{ICONS.get(w['level'], '⚪')} **{w['location']}** — "
                         f"{w['message']} ({w['value']}) · {w['time']}")

with tab_handoff:
    st.write("Going home? DataSurge writes the briefing for the next shift.")
    if st.button("📝 Write handoff note"):
        with st.spinner("Writing the handoff..."):
            st.session_state.handoff = ai.shift_handoff(warnings)
    if "handoff" in st.session_state:
        st.markdown(st.session_state.handoff)
        st.download_button("⬇️ Download note", st.session_state.handoff,
                           file_name="shift_handoff.md")
