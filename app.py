"""app.py - The DataSurge website (what the night-shift worker sees)."""
import streamlit as st

import ai
import autopilot

st.set_page_config(page_title="DataSurge", page_icon="⚡", layout="wide")

# ============================================================
#  Look & feel: navy, baby blue, black
# ============================================================
st.markdown("""
<style>
:root{
  --navy:#0B1F3A; --navy2:#12305A; --baby:#7EC8F2; --ice:#BFE6FF;
  --black:#04070F; --text:#E6F1FB; --muted:#8FA9C4;
  --red:#FF5C7A; --amber:#FFC857; --green:#5CE0A8;
}
.stApp{background:
  radial-gradient(1200px 600px at 10% -10%, rgba(126,200,242,.12), transparent 60%),
  radial-gradient(900px 500px at 110% 10%, rgba(18,48,90,.55), transparent 60%),
  var(--black);}
#MainMenu, footer, header{visibility:hidden;}
.block-container{padding-top:1.6rem; max-width:1250px;}
h1,h2,h3{letter-spacing:-.02em;}

.ds-hero{display:flex; align-items:center; justify-content:space-between;
  padding:22px 28px; border-radius:20px; margin-bottom:18px;
  background:linear-gradient(135deg, var(--navy) 0%, var(--navy2) 100%);
  border:1px solid rgba(126,200,242,.25);
  box-shadow:0 10px 40px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.04);}
.ds-logo{font-size:2.1rem; font-weight:800; color:var(--text); margin:0;}
.ds-logo span{color:var(--baby);}
.ds-tag{color:var(--muted); margin-top:2px;}
.ds-pill{padding:6px 14px; border-radius:999px; font-size:.8rem; font-weight:600;
  color:var(--ice); background:rgba(126,200,242,.12); border:1px solid rgba(126,200,242,.35);}

.ds-metric{padding:16px 18px; border-radius:16px; background:rgba(11,31,58,.75);
  border:1px solid rgba(126,200,242,.18);}
.ds-metric .k{color:var(--muted); font-size:.8rem; text-transform:uppercase; letter-spacing:.08em;}
.ds-metric .v{color:var(--text); font-size:1.9rem; font-weight:800; margin-top:4px;}

.ds-now{padding:22px 26px; border-radius:18px; margin:6px 0 10px;
  background:linear-gradient(135deg, rgba(255,92,122,.16), rgba(11,31,58,.9));
  border:1px solid rgba(255,92,122,.55);
  box-shadow:0 0 0 1px rgba(255,92,122,.15), 0 0 32px rgba(255,92,122,.18);}
.ds-now .lbl{color:var(--red); font-weight:800; letter-spacing:.12em; font-size:.78rem;}
.ds-now .msg{color:var(--text); font-size:1.5rem; font-weight:800; margin:6px 0 4px;}
.ds-now .meta{color:var(--muted);}

.ds-row{padding:12px 16px; border-radius:12px; margin-bottom:8px;
  background:rgba(11,31,58,.55); border:1px solid rgba(126,200,242,.12); color:var(--text);}
.ds-row b{color:var(--ice);}

.ds-rack{padding:14px; border-radius:14px; text-align:center; margin-bottom:10px;
  background:rgba(11,31,58,.8); border:1px solid rgba(126,200,242,.2);}
.ds-rack .n{color:var(--muted); font-size:.8rem;}
.ds-rack .t{font-size:1.6rem; font-weight:800;}
.ds-rack .j{color:var(--muted); font-size:.8rem;}
.ds-rack.hot{border-color:var(--red); box-shadow:0 0 22px rgba(255,92,122,.35);}
.ds-rack.warm{border-color:var(--amber);}

.ds-log{padding:10px 14px; border-left:3px solid var(--baby); margin-bottom:8px;
  background:rgba(126,200,242,.07); border-radius:0 10px 10px 0; color:var(--text);}

.stButton>button, .stDownloadButton>button{border-radius:10px; font-weight:600;
  border:1px solid rgba(126,200,242,.45); background:rgba(11,31,58,.9); color:var(--ice);}
.stButton>button:hover, .stDownloadButton>button:hover{border-color:var(--baby);
  color:#fff; box-shadow:0 0 16px rgba(126,200,242,.35);}
.stTabs [data-baseweb="tab-list"]{gap:6px;}
.stTabs [data-baseweb="tab"]{background:rgba(11,31,58,.6); border-radius:10px 10px 0 0;
  padding:8px 16px;}
div[data-testid="stExpander"]{background:rgba(11,31,58,.55); border-radius:12px;
  border:1px solid rgba(255,200,87,.35);}
</style>
""", unsafe_allow_html=True)

LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}
ICONS = {"critical": "🔴", "warning": "🟡", "info": "🟢"}
# Rough demo numbers: cost per hour if this turns into an outage.
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
        warnings, source = get_warnings(), "LIVE"
    except Exception:
        warnings, source = [dict(w) for w in FAKE_WARNINGS], "DEMO DATA"
    try:
        from brain import rank                 # Jotish: brain.py -> rank(warnings)
        warnings = rank(warnings)
    except Exception:
        warnings = sorted(warnings, key=lambda w: LEVEL_ORDER.get(w["level"], 9))
    return warnings, source


# ---- Memory between clicks ----
ss = st.session_state
ss.setdefault("status", {})
ss.setdefault("explanations", {})
ss.setdefault("racks", autopilot.new_racks())
ss.setdefault("ai_log", [])
ss.setdefault("approvals", [])

warnings, source = load_warnings()
for w in warnings:
    w["status"] = ss.status.get(w["id"], w.get("status", "open"))
open_ws = [w for w in warnings if w["status"] != "resolved"]


def explain_button(w, key_prefix):
    if st.button("🤖 Explain", key=f"{key_prefix}-explain-{w['id']}"):
        with st.spinner("DataSurge is thinking..."):
            ss.explanations[w["id"]] = ai.explain_warning(w)
    if w["id"] in ss.explanations:
        st.info(ss.explanations[w["id"]])


def action_buttons(w, key_prefix):
    c1, c2, _ = st.columns([1, 1, 4])
    if w["status"] == "open" and c1.button("👀 I'm on it", key=f"{key_prefix}-ack-{w['id']}"):
        ss.status[w["id"]] = "acknowledged"
        st.rerun()
    if c2.button("✅ Resolved", key=f"{key_prefix}-done-{w['id']}"):
        ss.status[w["id"]] = "resolved"
        st.toast(f"Resolved: {w['message']}", icon="✅")
        st.rerun()


# ============================================================
#  Header
# ============================================================
st.markdown(f"""
<div class="ds-hero">
  <div>
    <div class="ds-logo">⚡ Data<span>Surge</span></div>
    <div class="ds-tag">Your AI teammate for the night shift</div>
  </div>
  <div class="ds-pill">● {source}</div>
</div>
""", unsafe_allow_html=True)

# ---- Numbers at a glance ----
at_risk = sum(COST_PER_HOUR.get(w["level"], 0) for w in open_ws)
cards = [
    ("🔴 Critical", sum(w["level"] == "critical" for w in open_ws)),
    ("🟡 Warnings", sum(w["level"] == "warning" for w in open_ws)),
    ("🤖 Fixed by AI", len(ss.ai_log)),
    ("💸 At risk / hour (est.)", f"${at_risk:,}"),
]
for col, (k, v) in zip(st.columns(4), cards):
    col.markdown(f'<div class="ds-metric"><div class="k">{k}</div><div class="v">{v}</div></div>',
                 unsafe_allow_html=True)
st.write("")

tab_now, tab_auto, tab_handoff = st.tabs(["🚨 Right now", "🤖 Autopilot", "🔁 Shift handoff"])

# ============================================================
#  Tab 1: what needs the worker
# ============================================================
with tab_now:
    if not open_ws:
        st.success("🎉 All clear. Nothing needs you right now.")
    else:
        top = open_ws[0]
        st.markdown(f"""
        <div class="ds-now">
          <div class="lbl">🚨 NEEDS YOU NOW</div>
          <div class="msg">{top['message']}</div>
          <div class="meta">{top['location']} · reading {top['value']} · {top['time']} · {top['status']}</div>
        </div>""", unsafe_allow_html=True)
        explain_button(top, "top")
        action_buttons(top, "top")

        small = [w for w in open_ws[1:] if w["level"] == "warning"]
        if small:
            st.markdown("### 👁️ Don't forget: small issues that could grow")
            for w in small:
                with st.expander(f"🟡 {w['location']} — {w['message']}"):
                    st.write(f"Reading: {w['value']} · {w['time']} · status: {w['status']}")
                    explain_button(w, "small")
                    action_buttons(w, "small")

        rest = [w for w in open_ws[1:] if w["level"] != "warning"]
        if rest:
            st.markdown("### Everything else")
            for w in rest:
                st.markdown(f'<div class="ds-row">{ICONS.get(w["level"], "⚪")} <b>{w["location"]}</b>'
                            f' — {w["message"]} ({w["value"]}) · {w["time"]}</div>',
                            unsafe_allow_html=True)

# ============================================================
#  Tab 2: AI fixes things by itself
# ============================================================
with tab_auto:
    st.markdown("Less work means less heat. When a rack overheats, DataSurge **moves its jobs to "
                "cooler racks by itself**, and only asks you before anything risky.")

    b1, b2, _ = st.columns([1.4, 1, 3])
    if b1.button("🔥 Simulate cooling failure on Rack 12"):
        rack12 = next(r for r in ss.racks if r["name"] == "Rack 12")
        rack12["cooling_penalty"] = 7.0
        ss.racks_before = [dict(r) for r in ss.racks]
        ss.racks, actions, approvals = autopilot.run(ss.racks)
        ss.ai_log = actions + ss.ai_log
        ss.approvals = approvals
        for a in actions:
            st.toast(a, icon="🤖")
    if b2.button("↺ Reset demo"):
        ss.racks, ss.ai_log, ss.approvals = autopilot.new_racks(), [], []
        ss.pop("racks_before", None)
        st.rerun()

    def rack_grid(racks, title):
        st.markdown(f"#### {title}")
        for col, r in zip(st.columns(len(racks)), racks):
            t = autopilot.temp(r)
            cls = "hot" if t > autopilot.HOT_LIMIT else "warm" if t > autopilot.SAFE_TARGET else ""
            color = "#FF5C7A" if cls == "hot" else "#FFC857" if cls == "warm" else "#7EC8F2"
            col.markdown(f'<div class="ds-rack {cls}"><div class="n">{r["hall"]} · {r["name"]}</div>'
                         f'<div class="t" style="color:{color}">{t}°C</div>'
                         f'<div class="j">{r["jobs"]} jobs</div></div>', unsafe_allow_html=True)

    if "racks_before" in ss:
        rack_grid(ss.racks_before, "Before: cooling fails, Rack 12 overheats")
        rack_grid(ss.racks, "After: DataSurge moved the work")
    else:
        rack_grid(ss.racks, "Live racks")

    if ss.approvals:
        st.markdown("#### ✋ Needs your OK")
        for i, a in enumerate(ss.approvals):
            st.warning(a["text"])
            if st.button("Approve", key=f"approve-{i}"):
                ss.ai_log.insert(0, f"Worker approved: paused low-priority jobs on {a['rack']}.")
                ss.approvals.pop(i)
                st.rerun()

    st.markdown("#### 🤖 What DataSurge did by itself")
    if ss.ai_log:
        for line in ss.ai_log:
            st.markdown(f'<div class="ds-log">{line}</div>', unsafe_allow_html=True)
    else:
        st.caption("Nothing yet. Click 🔥 Simulate to see it in action.")

# ============================================================
#  Tab 3: shift handoff
# ============================================================
with tab_handoff:
    st.markdown("Going home? DataSurge writes the briefing for the next shift, "
                "including what the AI fixed by itself.")
    if st.button("📝 Write handoff note"):
        with st.spinner("Writing the handoff..."):
            fixed = [{"location": "autopilot", "message": line, "level": "info",
                      "status": "resolved", "value": "", "time": ""} for line in ss.ai_log]
            ss.handoff = ai.shift_handoff(warnings + fixed)
    if "handoff" in ss:
        st.markdown(ss.handoff)
        st.download_button("⬇️ Download note", ss.handoff, file_name="shift_handoff.md")
