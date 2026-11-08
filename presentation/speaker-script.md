# Datasurge — three-minute pitch

Six slides. Total: 180 seconds. Speaker notes are embedded in the PowerPoint.

## 1. Keep AI running. Keep people one step ahead. (0:00–0:15)

Behind every AI model is a data center, and a team keeping it alive around the clock. Datasurge helps that team see what is at risk, act with context, and pass the work on clearly.

## 2. The warning exists. The response breaks down. (0:15–0:40)

The challenge is not just detecting failures. An important warning gets buried among routine alerts. A night-shift engineer leaves without passing on an unresolved issue. Or an incident reaches someone who cannot fix it. These are gaps between monitoring and coordinated action. We built Datasurge around those three gaps.

## 3. One cooling fault. A chain of consequences. (0:40–1:10)

Here is our example: a cooling failure in us-east. The dependency map connects that chiller to the racks, GPUs, and workloads that depend on it. Selecting a component highlights downstream risk and shows affected workloads, customer exposure, and estimated time to impact. Operators can also preview maintenance in what-if mode. These are simulated forecasts, not measurements from real hardware.

## 4. Give the right person a clear next step. (1:10–1:40)

Related alerts are grouped into an incident and routed to an on-shift specialist. If nobody acknowledges it, the incident escalates. The workload planner evaluates capacity, hardware, latency, and risk before suggesting a move. An operator approves the action. If a workload cannot move safely, checkpointing may be the right option. The timeline records what happened and who acted.

## 5. A shift change should not erase what you know. (1:40–2:10)

At shift change, Datasurge carries forward open incidents, watch items, pending migrations, and commitments to other teams. The incoming engineer acknowledges each item. Gemini is a separate assistant for questions about the current simulation. Handoff reports still have an offline template path, so the core demo does not depend on an AI response. The assistant explains; operators control actions.

## 6. One incident. A complete operational story. (2:10–3:00)

Switch to the prepared app. Say: I am triggering a cooling failure in us-east. This is the component that failed, and these are the workloads downstream. The incident has an owner and an acknowledgment countdown. Here is a workload recommendation and the reasoning behind it. Finally, the handoff keeps the next engineer informed and asks them to acknowledge the open work. Close with: Datasurge connects a warning to its impact, its owner, and its next action—so the team can stay one step ahead.

## Before presenting

- Start the app and test Gemini ahead of time. Do not wait for an AI response on stage.
- Reset the simulation, select us-east, and rehearse the cooling-failure preset.
- Keep the app in a second tab. Prepare the shift handoff in advance if advancing the simulation takes too long.
- Show one migration recommendation. Do not wait for every workload to finish moving.
- Impact estimates and migration targets depend on simulation state. Describe only what the app shows.
- Gemini powers interactive Q&A. Reports retain the existing Claude/template path; no Claude key is currently configured.
- The graph uses dependency columns, not a radial mind map.
- This is a simulated prototype. Do not claim measured outage reduction, production deployment, or customer traction.

## 50-second demo cue sheet

| Time | Action | Say |
| --- | --- | --- |
| 0–10 s | Trigger cooling failure in us-east. | One fault starts the chain. |
| 10–20 s | Select the affected chiller. | Here are its downstream workloads and predicted risk. |
| 20–30 s | Open the incident. | A specialist owns it; silence triggers escalation. |
| 30–40 s | Show a workload suggestion; approve if ready. | We explain the move before asking for approval. |
| 40–50 s | Show the prepared handoff and acknowledge an item. | The next engineer receives the context, not just the alert. |

If no recommendation is ready, describe the planner without claiming a completed migration. If the live app fails, narrate slide 6.

## Opening the deck

Open datasurge-pitch.pptx in PowerPoint, Keynote, or Google Slides.
Or open datasurge-pitch.html in a browser: arrow keys navigate, F requests fullscreen, N toggles notes.
