# datasurge — AI data center operations console

A live, demo-ready ops console for a **simulated** AI data center. It helps the
operations team stay one step ahead of the three classic failure modes:

| Failure mode | How datasurge addresses it |
|---|---|
| **Missed warning** | Predictive alerts ("rack B4 reaches thermal limit in ~12 min"), priority scoring, de-dup + grouping so the real problem isn't buried, and auto-escalation with a visible countdown (re-notify → backup → shift lead). |
| **Unclear handoff** | Auto-generated shift handoff report (Claude or template) with per-item **Acknowledge handoff**; overdue items escalate to the incoming lead. Notes can be tagged as *promises to other teams* or *things to watch* so they carry over. |
| **Wrong info at the wrong time** | Blast-radius panel with ETAs, customers and SLA exposure; routing by specialization and load; a personal **My view** with only your incidents, the relevant graph slice and the runbook. |

## Quick start

```bash
./run.sh            # dev: backend :8000 + Vite :5173  → open http://localhost:5173
./run.sh prod       # build frontend, serve everything → open http://localhost:8000
```

Optional, to enable Claude summaries:

```bash
cp backend/.env.example backend/.env   # then set ANTHROPIC_API_KEY=...
```

Without a key (or offline), every AI feature falls back to a template summary and the UI shows **Template fallback**.

Requirements: Python 3.10+ and Node 20+.

## Demo script (≈5 minutes)

1. **Console** opens on the night shift at 05:30, 30 simulated minutes before the 06:00 handoff. The clock runs at 10×.
2. Click **Trigger incident → Cooling failure** (us-east Chiller CH-1).
   - The chiller node pulses. Racks B4–B9 turn yellow with ETA badges, and the blast-radius panel reads *"Racks B4–B9 reach thermal limit (35°C) in ~12 min"*. It also lists affected workloads, customers and $/hr SLA exposure, including the cross-region failover to us-central.
   - One **P1** incident appears, routed to the on-shift cooling specialist, with an ack countdown. As racks heat up, 10–30 alerts are grouped into it (watch the noise-reduction stat).
3. Don't acknowledge it. Watch it **escalate**: re-notify, then backup, then shift lead, all logged in the timeline.
4. Open **Workload handoff**. Inference endpoints get move suggestions with reasoning: capacity, GPU type, latency vs SLO, cost and egress, risk, and time vs ETA. Orion-70B (32× H100) has nowhere to go, so datasurge suggests **checkpoint now**. Approve a few, or flip **Auto-approve low-risk moves**.
5. Open the incident (**Details**) and **Dispatch repair**. When the chiller recovers, alerts clear and the incident auto-resolves. **AI summary** shows what broke, root cause, actions, what worked and what didn't.
6. Add a note tagged **Promise to another team**, then skip ahead (⏩) past 06:00. A **handoff report** is generated. Switch the viewer (top right) to a day-shift engineer and **Acknowledge handoff** for each item.
7. Try **What-if mode**: click *UPS-1* and *Spine-2* to preview the maintenance impact before doing anything, then **Start maintenance**.
8. Other presets show different behaviors:
   - **Power feed loss**: UPS on battery, then a cooling cascade.
   - **ToR flapping**: same-region move, low risk, EU data residency respected.
   - **Storage degradation**: data handoff to the other cluster.
   - **GPU ECC**: the GPU falls off the bus in ~20 min, and the job crashes unless it was checkpointed or moved.

## Architecture

```
┌──────────────────────────── Browser (React + TS + Tailwind) ────────────────────────────┐
│ TopBar (sim clock/speed, Trigger incident, viewer)   SideNav (pages + badges)           │
│ Console: [ Dependency graph (React Flow + minimap) | Blast panel ]  [ Incident queue ]  │
│          [ Timeline ]                                                                   │
│ Pages: Incidents · Workload handoff · Shift handoff · On-call · My view                │
└──────────────▲───────────────── WebSocket /ws (full state, 2×/s) ───────────────────────┘
               │  REST /api/* (actions: ack, approve, inject, what-if…)
┌──────────────┴────────────────────────── FastAPI (Python) ──────────────────────────────┐
│ main.py      routes + WS broadcaster + 0.5 s ticker                                     │
│ engine.py    owns state; step(dt) = sim → incidents → migrations → shift/handoff        │
│ topology.py  YAML → DAG; propagate(): own status → effective status + forecast/ETA      │
│ simulation.py clock, telemetry physics (thermal, battery, loss, ECC, disks), faults     │
│ incidents.py alert rules, de-dup, grouping by root cause, priority score, routing,      │
│              escalation ladder                                                          │
│ migrations.py target selection + reasoning, checkpoint/drain/data-move execution        │
│ reports.py   incident summaries & shift handoff (Claude, template fallback)             │
│ llm.py       Claude API client (ANTHROPIC_API_KEY from env / backend/.env)              │
└──────────────┬──────────────────────────────────────────────────────────────────────────┘
               │ seed data
      backend/data/topology.yaml · roster.yaml · runbooks.yaml
```

**State** is in memory and seeded from YAML. Reset from the top bar (↺) reloads the YAML, so you can edit the data center and reset.

### How impact propagation works

Every component has an *own* condition (from the simulator) and an *effective* condition (own plus everything upstream).
Edges are typed (`power`, `cooling`, `network`, `host`, `storage`, `replication`, `failover`), and each type maps an upstream status to a downstream impact. Dual-corded power and dual spines are **redundant groups** (`min: 1`): losing one member makes dependents *at risk* rather than *down*.
Kind-specific rules add time: a UPS that loses its feed runs on battery (forecast: down in `runtime × battery%`). A rack that loses cooling gets an exponential thermal forecast to 35 °C and then 40 °C.
Forecasts flow downstream, so a workload knows it will be impacted in ~12 min before anything has failed.

* **Click a node.** If it is healthy, you see its hypothetical blast radius ("if this fails"). If it is faulted, you see its live impact.
* **What-if.** Select several nodes; they are treated as down for maintenance, and the result is compared against the current state.

### Priority score (0–100)

`severity (≤40) + blast radius (≤20) + SLA impact by tier (≤20) + time to impact (≤15) + related alerts (≤10)` gives P1 (≥70), P2 (≥50), P3 (≥30) or P4.
Ack windows per escalation step: P1 3 min, P2 8 min, P3 15 min, P4 30 min (simulated; set in `roster.yaml`).

### Grouping

A new alert joins an open incident whose root is the alert's computed root cause, or is upstream of the alert's component. If a new root cause appears *upstream* of existing incidents, those incidents are merged into it. Flapping alerts reopen the same alert with ×N instead of creating new ones.

## Folder structure

```
datasurge-new/
├── run.sh                    # one-command start (dev or prod)
├── README.md
├── backend/
│   ├── requirements.txt      # fastapi, uvicorn, pyyaml, anthropic
│   ├── .env.example          # ANTHROPIC_API_KEY, DATASURGE_MODEL, DATASURGE_LLM=off
│   ├── data/
│   │   ├── topology.yaml     # regions, components, dependencies, workloads, customers, presets
│   │   ├── roster.yaml       # shifts, engineers + specializations, ack timeouts
│   │   └── runbooks.yaml     # per-category runbooks
│   ├── app/
│   │   ├── main.py           # FastAPI REST + WebSocket
│   │   ├── engine.py         # orchestration, blast radius, handoff, snapshot
│   │   ├── topology.py       # graph + propagation
│   │   ├── simulation.py     # clock, telemetry, faults
│   │   ├── incidents.py      # alerts, grouping, priority, routing, escalation
│   │   ├── migrations.py     # smart workload/data handoff
│   │   ├── reports.py        # AI incident summary + shift handoff (with templates)
│   │   └── llm.py            # Claude client
│   └── tests/test_scenarios.py
└── frontend/
    ├── vite.config.ts        # Tailwind v4 + proxy /api and /ws → :8000
    └── src/
        ├── App.tsx           # shell + page switch
        ├── index.css         # blue console theme tokens
        ├── lib/              # api.ts (REST + live WS hook), ctx.tsx (app context), types.ts
        ├── components/
        │   ├── Shell.tsx         # TopBar, SideNav, trigger modal, viewer switcher
        │   ├── graph/            # TopologyGraph.tsx (React Flow + minimap), layout.ts
        │   ├── Panels.tsx        # BlastPanel, IncidentQueue/Card, Timeline, MigrationCard
        │   ├── IncidentDrawer.tsx
        │   └── ui.tsx            # badges, cards, buttons, markdown
        └── pages/            # ConsolePage, OtherPages (incidents, migrations, handoff, on-call, my view)
```

## API (selection)

| Method | Path | Purpose |
|---|---|---|
| WS | `/ws` | live state (and topology when it changes) |
| GET | `/api/topology`, `/api/state`, `/api/blast/{node}` | reads |
| POST | `/api/whatif` `{nodes}` | hypothetical blast radius |
| POST | `/api/incidents/trigger` `{preset, target}` | inject a fault |
| POST | `/api/sim/speed` `{speed}` · `/api/sim/pause` · `/api/sim/advance` `{minutes}` · `/api/sim/reset` | clock |
| POST | `/api/incidents/{id}/ack · /resolve · /repair · /note · /summary` | incident actions (`actor` = engineer id) |
| POST | `/api/migrations/{id}/approve · /reject`, `/api/migrations/auto` | handoff |
| POST | `/api/maintenance/start` `{nodes}` · `/api/maintenance/end` | what-if → real maintenance |
| POST | `/api/handoff/generate`, `/api/handoff/{id}/items/{item}/ack` | shift handoff |

## LLM

`llm.py` calls Claude through the official `anthropic` SDK. The model defaults to `claude-opus-5-5` at low effort (summaries should be quick in a live demo); override it with `DATASURGE_MODEL` / `DATASURGE_EFFORT`.
Server-side refusal fallbacks are enabled (`fallbacks: "default"`).
Any missing key, network error, rate limit or refusal makes datasurge use the deterministic template, and the UI shows the reason.

## Gemini assistant

Set `GEMINI_API_KEY=your-key` in `backend/.env` and restart the backend. Optional: `GEMINI_MODEL=gemini-3.8-flash`. The key stays on the backend. Open **Ask datasurge** to ask questions with the current simulation snapshot. Without a key, the assistant shows setup guidance; existing offline summaries remain available. Questions are independent and do not execute operations.
