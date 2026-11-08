"""app.py - The DataSurge website (what the night-shift worker sees)."""
import streamlit as st

import ai
import autopilot

st.set_page_config(page_title="DataSurge · Operations", page_icon="⚡", layout="wide",
                   initial_sidebar_state="expanded")

# ============================================================
#  Look & feel: navy, baby blue, black
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{
  /* palette */
  --baby:#AAD6EC; --steel:#81B1CE; --indigo:#151269; --deep:#0F1056; --navy:#113065;
  --bg:#0B0C40;                         /* a touch darker than deep indigo */
  --card:#121159; --line:rgba(170,214,236,.22); --line-strong:rgba(170,214,236,.5);
  --text:#E4EEF5; --muted:#8FAFC6; --red:#E8657E; --amber:#E6BE63;
}
/* ---------- page ---------- */
.stApp{background:var(--bg);}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.4rem; max-width:1250px;}
p, li, label{color:var(--text);}
h1,h2,h3,h4, h1 *, h2 *, h3 *, h4 *{color:var(--baby) !important; letter-spacing:-.01em;}
[data-testid="stMarkdownContainer"] h3{border-bottom:1px solid var(--line); padding-bottom:6px;
  margin-top:14px; font-weight:700;}
a{color:var(--baby) !important;}

/* ---------- header ---------- */
.ds-hero{position:relative; display:flex; align-items:center; justify-content:space-between;
  padding:22px 28px; border-radius:18px; margin-bottom:16px; overflow:hidden;
  background:var(--navy); border:1px solid var(--line-strong);}
.ds-hero:before{content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--baby);}
.ds-logo{font-size:2.1rem; font-weight:800; color:var(--text); margin:0;}
.ds-logo span{color:var(--baby);}
.ds-tag{color:var(--muted); margin-top:2px;}
.ds-pill{padding:5px 13px; border-radius:999px; font-size:.75rem; font-weight:700;
  color:var(--baby); border:1px solid var(--baby); background:rgba(170,214,236,.08);}

/* ---------- stat cards ---------- */
.ds-metric{padding:15px 18px; border-radius:14px; background:var(--card);
  border:1px solid var(--line); border-top:3px solid var(--baby);}
.ds-metric .k{color:var(--steel); font-size:.75rem; text-transform:uppercase; letter-spacing:.08em;}
.ds-metric .v{color:var(--baby); font-size:1.85rem; font-weight:800; margin-top:4px;}

/* ---------- tabs ---------- */
.stTabs [role="tablist"]{gap:6px; border-bottom:1px solid rgba(170,214,236,.3);}
.stTabs [role="tab"]{background:transparent !important; border:none !important;
  border-bottom:2px solid transparent !important; border-radius:0; padding:10px 16px !important;}
.stTabs [role="tab"] p{color:var(--steel); font-weight:600; font-size:.95rem;}
.stTabs [aria-selected="true"]{border-bottom:2px solid var(--baby) !important;}
.stTabs [aria-selected="true"] p{color:var(--baby) !important;}

/* ---------- needs you now ---------- */
.ds-now{padding:20px 24px; border-radius:16px; margin:8px 0 12px;
  background:var(--card); border:1px solid rgba(232,101,126,.6); border-left:5px solid var(--red);}
.ds-now .lbl{color:var(--red); font-weight:800; letter-spacing:.12em; font-size:.75rem;}
.ds-now .msg{color:var(--text); font-size:1.5rem; font-weight:800; margin:6px 0 4px;}
.ds-now .meta{color:var(--muted);}

/* ---------- lists ---------- */
.ds-row{padding:11px 15px; border-radius:10px; margin-bottom:8px; color:var(--text);
  background:var(--card); border:1px solid var(--line); border-left:3px solid var(--baby);}
.ds-row b{color:var(--baby);}
div[data-testid="stExpander"]{background:var(--card); border-radius:10px;
  border:1px solid var(--line) !important; border-left:3px solid var(--amber) !important;}
div[data-testid="stExpander"] summary p{color:var(--text) !important;}

/* ---------- racks ---------- */
.ds-rack{padding:13px 8px; border-radius:12px; text-align:center; margin-bottom:10px;
  background:var(--card); border:1px solid var(--line-strong);}
.ds-rack .n{color:var(--muted); font-size:.75rem;}
.ds-rack .t{font-size:1.5rem; font-weight:800;}
.ds-rack .j{color:var(--muted); font-size:.75rem;}
.ds-rack.hot{border:1.5px solid var(--red); background:rgba(232,101,126,.08);}
.ds-rack.warm{border:1.5px solid var(--amber);}

/* ---------- AI log ---------- */
.ds-log{padding:10px 14px; border-left:3px solid var(--baby); margin-bottom:8px; color:var(--text);
  background:var(--card); border-radius:0 10px 10px 0;}

/* ---------- buttons (outlined, fill on hover) ---------- */
.stButton>button, .stDownloadButton>button{border-radius:9px; font-weight:600;
  background:rgba(170,214,236,.06); color:var(--baby); border:1px solid rgba(170,214,236,.6);
  padding:.4rem .9rem; transition:all .15s ease;}
.stButton>button p, .stDownloadButton>button p{color:var(--baby) !important;}
.stButton>button:hover, .stDownloadButton>button:hover{background:rgba(170,214,236,.12);
  border-color:var(--baby); color:var(--baby);}

/* ---------- AI answer boxes ---------- */
div[data-testid="stAlert"]{background:var(--card) !important; border-radius:10px; border:1px solid var(--line);}

/* ---------- professional details ---------- */
html, body, .stApp, p, li, label, button, input{font-family:'Inter', -apple-system, sans-serif !important;}
.ds-brand{display:flex; align-items:center; gap:12px;}
.ds-mark{width:34px; height:34px; border-radius:8px; background:var(--baby);
  display:flex; align-items:center; justify-content:center; color:var(--bg); font-weight:800; font-size:1rem;}
.ds-logo{font-size:1.45rem !important; font-weight:700 !important; letter-spacing:-.01em;}
.ds-right{display:flex; align-items:center; gap:14px; color:var(--muted); font-size:.85rem;}
.ds-section{color:var(--baby); font-size:.72rem; font-weight:600; text-transform:uppercase;
  letter-spacing:.12em; margin:22px 0 10px; padding-bottom:6px; border-bottom:1px solid rgba(170,214,236,.3);}
.dot{display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:8px; vertical-align:middle;}
.dot.critical{background:var(--red);} .dot.warning{background:var(--amber);}
.dot.info{background:var(--steel);} .dot.ok{background:#6FCF97;}
.ds-row{display:flex; justify-content:space-between; align-items:center;}
.ds-row .when{white-space:nowrap; margin-left:12px; color:var(--muted); font-size:.82rem; font-variant-numeric:tabular-nums;}
.ds-metric .v, .ds-rack .t{font-variant-numeric:tabular-nums;}
.ds-now .msg{font-size:1.3rem !important; font-weight:700 !important;}
.ds-metric .v{font-size:1.6rem !important; font-weight:700 !important;}
.ds-hero{padding:16px 22px !important; border-radius:12px !important;}
.ds-metric, .ds-now, .ds-rack, .ds-row, .ds-log{border-radius:10px !important;}
.ds-desc{color:var(--muted); font-size:.92rem; margin:6px 0 14px;}
.ds-pill, .ds-right span{white-space:nowrap;}
@media (max-width:900px){ .ds-right > span{display:none;} .ds-tag{font-size:.8rem;} }

/* ---------- website shell: sidebar ---------- */
[data-testid="stSidebar"]{background:var(--navy); border-right:1px solid rgba(170,214,236,.18);}
[data-testid="stSidebar"] > div{padding-top:0;}
.sb-brand{display:flex; align-items:center; gap:10px; padding:6px 4px 18px; margin-bottom:10px;
  border-bottom:1px solid rgba(170,214,236,.18);}
.sb-brand .name{font-weight:700; font-size:1.15rem; color:var(--text);}
.sb-brand .name span{color:var(--baby);}
.sb-label{color:var(--steel); font-size:.68rem; font-weight:600; letter-spacing:.14em;
  text-transform:uppercase; margin:6px 0 6px 4px;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px;}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:9px 12px; border-radius:8px; margin:0;
  width:100%; cursor:pointer; transition:background .12s ease;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(170,214,236,.08);}
[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:not([data-testid]){display:none;}   /* hide radio circles */
[data-testid="stSidebar"] [role="radiogroup"] label p{color:var(--steel); font-weight:500; font-size:.93rem;}
[data-testid="stSidebar"] [role="radiogroup"] label[data-selected="true"]{background:rgba(170,214,236,.14);
  box-shadow:inset 3px 0 0 var(--baby);}
[data-testid="stSidebar"] [role="radiogroup"] label[data-selected="true"] p{color:var(--baby); font-weight:600;}
.sb-card{margin-top:18px; padding:12px; border-radius:10px; background:rgba(170,214,236,.06);
  border:1px solid rgba(170,214,236,.18); font-size:.82rem; color:var(--steel);}
.sb-card b{color:var(--text); font-weight:600;}
.sb-user{display:flex; align-items:center; gap:10px; margin-top:18px; padding-top:14px;
  border-top:1px solid rgba(170,214,236,.18);}
.avatar{width:32px; height:32px; border-radius:50%; background:var(--baby); color:var(--bg);
  display:flex; align-items:center; justify-content:center; font-weight:700; font-size:.8rem;}
.sb-user .who{font-size:.85rem; color:var(--text); line-height:1.2;}
.sb-user .who small{color:var(--steel);}

/* ---------- website shell: top bar ---------- */
.topbar{display:flex; align-items:center; justify-content:space-between; margin:-8px 0 18px;
  padding-bottom:14px; border-bottom:1px solid rgba(170,214,236,.18);}
.crumb{color:var(--steel); font-size:.8rem;}
.crumb b{color:var(--baby); font-weight:500;}
.ptitle{font-size:1.6rem; font-weight:700; color:var(--text); margin-top:2px;}
.top-right{display:flex; align-items:center; gap:10px;}
.search{width:240px; padding:8px 12px; border-radius:8px; color:var(--steel); font-size:.85rem;
  background:var(--card); border:1px solid rgba(170,214,236,.22);}
.iconbtn{width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center;
  border:1px solid rgba(170,214,236,.22); background:var(--card); color:var(--baby); position:relative;}
.iconbtn .badge{position:absolute; top:-5px; right:-5px; min-width:16px; height:16px; border-radius:8px;
  background:var(--red); color:#fff; font-size:.62rem; font-weight:700; display:flex;
  align-items:center; justify-content:center; padding:0 4px;}
.site-footer{margin-top:40px; padding:16px 0 4px; border-top:1px solid rgba(170,214,236,.15);
  display:flex; justify-content:space-between; color:var(--steel); font-size:.78rem;}
@media (max-width:900px){ .search{display:none;} }
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

for msg in ss.pop("pending_toasts", []):
    st.toast(msg)

LEVEL_LABEL = {"critical": "Critical", "warning": "Warning", "info": "Info"}
STATUS_LABEL = {"open": "Open", "acknowledged": "Acknowledged", "resolved": "Resolved"}


def section(title):
    st.markdown(f'<div class="ds-section">{title}</div>', unsafe_allow_html=True)


def controls(w, key_prefix):
    """Explain / Acknowledge / Resolve in one row, AI analysis underneath."""
    c1, c2, c3, _ = st.columns([1, 1, 1, 3], gap="small")
    if c1.button("Explain", key=f"{key_prefix}-explain-{w['id']}", use_container_width=True):
        with st.spinner("Analyzing..."):
            ss.explanations[w["id"]] = ai.explain_warning(w)
    if w["status"] == "open" and c2.button("Acknowledge", key=f"{key_prefix}-ack-{w['id']}",
                                           use_container_width=True):
        ss.status[w["id"]] = "acknowledged"
        st.rerun()
    if c3.button("Resolve", key=f"{key_prefix}-done-{w['id']}", use_container_width=True):
        ss.status[w["id"]] = "resolved"
        st.toast(f"Resolved: {w['message']}")
        st.rerun()
    if w["id"] in ss.explanations:
        st.info(ss.explanations[w["id"]])


# ============================================================
#  Sidebar (website navigation)
# ============================================================
PAGES = ["Overview", "Priority queue", "Autopilot", "Shift handoff"]
with st.sidebar:
    st.markdown("""
    <div class="sb-brand"><div class="ds-mark">DS</div>
      <div class="name">Data<span>Surge</span></div></div>
    <div class="sb-label">Operations</div>""", unsafe_allow_html=True)
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.markdown(f"""
    <div class="sb-card"><b>Facility</b><br>Dallas DC-1 · Halls A–C<br><br>
      <b>Shift</b><br>Night · 10:00 PM – 7:00 AM<br><br>
      <b>Data source</b><br><span class="dot {'ok' if source == 'LIVE' else 'info'}"></span>{source.title()}</div>
    <div class="sb-user"><div class="avatar">OP</div>
      <div class="who">Night Operator<br><small>Critical Facilities</small></div></div>
    """, unsafe_allow_html=True)

# ============================================================
#  Top bar
# ============================================================
n_alerts = sum(w["level"] in ("critical", "warning") for w in open_ws)
st.markdown(f"""
<div class="topbar">
  <div><div class="crumb">DataSurge / <b>{page}</b></div><div class="ptitle">{page}</div></div>
  <div class="top-right">
    <div class="search">Search racks, alerts…</div>
    <div class="iconbtn" title="Alerts">&#128276;<span class="badge">{n_alerts}</span></div>
    <div class="avatar">OP</div>
  </div>
</div>
""", unsafe_allow_html=True)


def metrics_row():
    at_risk = sum(COST_PER_HOUR.get(w["level"], 0) for w in open_ws)
    cards = [
        ('<span class="dot critical"></span>Critical', sum(w["level"] == "critical" for w in open_ws)),
        ('<span class="dot warning"></span>Warnings', sum(w["level"] == "warning" for w in open_ws)),
        ('<span class="dot ok"></span>Auto-resolved', len(ss.ai_log)),
        ('<span class="dot info"></span>Est. exposure / hr', f"${at_risk:,}"),
    ]
    for col, (k, v) in zip(st.columns(4), cards):
        col.markdown(f'<div class="ds-metric"><div class="k">{k}</div><div class="v">{v}</div></div>',
                     unsafe_allow_html=True)


def rack_grid(racks, title):
    section(title)
    for col, r in zip(st.columns(len(racks)), racks):
        t = autopilot.temp(r)
        cls = "hot" if t > autopilot.HOT_LIMIT else "warm" if t > autopilot.SAFE_TARGET else ""
        color = "#E8657E" if cls == "hot" else "#E6BE63" if cls == "warm" else "#AAD6EC"
        col.markdown(f'<div class="ds-rack {cls}"><div class="n">{r["hall"]} · {r["name"]}</div>'
                     f'<div class="t" style="color:{color}">{t}°C</div>'
                     f'<div class="j">{r["jobs"]} jobs</div></div>', unsafe_allow_html=True)


def priority_card(top):
    st.markdown(f"""
    <div class="ds-now">
      <div class="lbl">PRIORITY 1 · {LEVEL_LABEL.get(top['level'], top['level']).upper()}</div>
      <div class="msg">{top['message']}</div>
      <div class="meta">{top['location']} &nbsp;·&nbsp; Reading {top['value']} &nbsp;·&nbsp;
        {top['time']} &nbsp;·&nbsp; {STATUS_LABEL.get(top['status'], top['status'])}</div>
    </div>""", unsafe_allow_html=True)


def event_row(w):
    st.markdown(f'<div class="ds-row"><span><span class="dot {w["level"]}"></span>'
                f'<b>{w["location"]}</b> — {w["message"]} ({w["value"]})</span>'
                f'<span class="when">{w["time"]}</span></div>', unsafe_allow_html=True)


# ============================================================
#  Page: Overview
# ============================================================
if page == "Overview":
    metrics_row()
    left, right = st.columns([3, 2], gap="large")
    with left:
        section("Top priority")
        if open_ws:
            priority_card(open_ws[0])
        else:
            st.success("All clear. No open issues.")
        section("Recent events")
        for w in open_ws[1:5]:
            event_row(w)
    with right:
        section("Recent autonomous actions")
        if ss.ai_log:
            for line in ss.ai_log[:4]:
                st.markdown(f'<div class="ds-log">{line}</div>', unsafe_allow_html=True)
        else:
            st.caption("No actions yet. Run a simulation from Autopilot.")
        section("Facility health")
        hot = sum(autopilot.temp(r) > autopilot.HOT_LIMIT for r in ss.racks)
        st.markdown(f'<div class="ds-row"><span><span class="dot ok"></span>Racks online</span>'
                    f'<span class="when">{len(ss.racks)}/{len(ss.racks)}</span></div>'
                    f'<div class="ds-row"><span><span class="dot {"critical" if hot else "ok"}"></span>'
                    f'Racks over thermal limit</span><span class="when">{hot}</span></div>'
                    f'<div class="ds-row"><span><span class="dot info"></span>Avg rack temperature</span>'
                    f'<span class="when">{sum(autopilot.temp(r) for r in ss.racks)/len(ss.racks):.1f}°C</span></div>',
                    unsafe_allow_html=True)

# ============================================================
#  Page: Priority queue
# ============================================================
elif page == "Priority queue":
    metrics_row()
    if not open_ws:
        st.success("All clear. No open issues.")
    else:
        section("Priority 1")
        priority_card(open_ws[0])
        controls(open_ws[0], "top")

        small = [w for w in open_ws[1:] if w["level"] == "warning"]
        if small:
            section("Watch list · minor issues that can escalate")
            for w in small:
                with st.expander(f"{w['location']}  —  {w['message']}"):
                    st.markdown(f'<div class="ds-desc">Reading {w["value"]} · {w["time"]} · '
                                f'{STATUS_LABEL.get(w["status"], w["status"])}</div>',
                                unsafe_allow_html=True)
                    controls(w, "small")

        rest = [w for w in open_ws[1:] if w["level"] != "warning"]
        if rest:
            section("Other events")
            for w in rest:
                event_row(w)

# ============================================================
#  Page: Autopilot
# ============================================================
elif page == "Autopilot":
    st.markdown('<div class="ds-desc">When a rack exceeds its thermal limit, DataSurge rebalances '
                'workload to cooler racks with spare capacity. Actions that affect power or '
                'availability require operator approval.</div>', unsafe_allow_html=True)

    b1, b2, _ = st.columns([2.2, 0.8, 2.6])
    if b1.button("Simulate cooling failure · Rack 12", use_container_width=True):
        rack12 = next(r for r in ss.racks if r["name"] == "Rack 12")
        rack12["cooling_penalty"] = 7.0
        ss.racks_before = [dict(r) for r in ss.racks]
        ss.racks, actions, approvals = autopilot.run(ss.racks)
        ss.ai_log = actions + ss.ai_log
        ss.approvals = approvals
        ss.pending_toasts = actions
        st.rerun()
    if b2.button("Reset", use_container_width=True):
        ss.racks, ss.ai_log, ss.approvals = autopilot.new_racks(), [], []
        ss.pop("racks_before", None)
        st.rerun()

    if "racks_before" in ss:
        rack_grid(ss.racks_before, "Before · cooling failure on Rack 12")
        rack_grid(ss.racks, "After · workload rebalanced by DataSurge")
    else:
        rack_grid(ss.racks, "Rack status")

    if ss.approvals:
        section("Pending operator approval")
        for i, a in enumerate(ss.approvals):
            st.warning(a["text"])
            if st.button("Approve", key=f"approve-{i}"):
                ss.ai_log.insert(0, f"Operator approved: paused low-priority jobs on {a['rack']}.")
                ss.approvals.pop(i)
                st.rerun()

    section("Autonomous actions log")
    if ss.ai_log:
        for line in ss.ai_log:
            st.markdown(f'<div class="ds-log">{line}</div>', unsafe_allow_html=True)
    else:
        st.caption("No actions taken yet.")

# ============================================================
#  Page: Shift handoff
# ============================================================
elif page == "Shift handoff":
    st.markdown('<div class="ds-desc">Generates a briefing for the incoming shift: overnight events, '
                'open issues by priority, and autonomous actions taken.</div>', unsafe_allow_html=True)
    if st.button("Generate handoff report"):
        with st.spinner("Generating report..."):
            fixed = [{"location": "autopilot", "message": line, "level": "info",
                      "status": "resolved", "value": "", "time": ""} for line in ss.ai_log]
            ss.handoff = ai.shift_handoff(warnings + fixed)
    if "handoff" in ss:
        st.markdown(ss.handoff)
        st.download_button("Download report", ss.handoff, file_name="shift_handoff.md")

# ============================================================
#  Footer
# ============================================================
st.markdown("""
<div class="site-footer"><span>© 2026 DataSurge · Built at HackUTD for CBRE &amp; NMC²</span>
<span>Status: <span class="dot ok"></span>All services operational</span></div>
""", unsafe_allow_html=True)
