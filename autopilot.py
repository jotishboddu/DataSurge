"""autopilot.py - The part of DataSurge that FIXES things by itself.

Safe actions (AI does them alone):  move jobs off an overheating rack.
Risky actions (AI asks first):      anything touching power or shutting things down.

Demo physics: a rack's temperature = room temp + heat from jobs + cooling problem.
Less work -> less heat, so moving jobs to a cooler rack cools the hot one down.
"""
import copy

ROOM_TEMP = 20.0       # deg C
HEAT_PER_JOB = 1.2     # deg C added per running job
HOT_LIMIT = 32.0       # above this, autopilot steps in
SAFE_TARGET = 29.0     # autopilot moves jobs until the rack is predicted below this
CAPACITY = 10          # max jobs one rack can run

DEMO_RACKS = [
    {"name": "Rack 03", "hall": "Hall A", "jobs": 4, "cooling_penalty": 0.0},
    {"name": "Rack 07", "hall": "Hall A", "jobs": 3, "cooling_penalty": 0.0},
    {"name": "Rack 12", "hall": "Hall B", "jobs": 7, "cooling_penalty": 0.0},
    {"name": "Rack 15", "hall": "Hall B", "jobs": 6, "cooling_penalty": 0.5},
    {"name": "Rack 21", "hall": "Hall C", "jobs": 5, "cooling_penalty": 0.0},
    {"name": "Rack 24", "hall": "Hall C", "jobs": 2, "cooling_penalty": 0.0},
]


def temp(rack, jobs=None):
    jobs = rack["jobs"] if jobs is None else jobs
    return round(ROOM_TEMP + jobs * HEAT_PER_JOB + rack["cooling_penalty"], 1)


def new_racks():
    return copy.deepcopy(DEMO_RACKS)


def run(racks):
    """Look at every rack, fix what is safe to fix, and report what needs a human.

    Returns (racks, actions, approvals)
      actions   - things the AI already did by itself
      approvals - risky things the AI wants the worker to OK first
    """
    actions, approvals = [], []
    for hot in sorted(racks, key=temp, reverse=True):
        if temp(hot) <= HOT_LIMIT:
            continue
        before = temp(hot)
        moved_to = {}
        while temp(hot) > SAFE_TARGET and hot["jobs"] > 0:
            # coolest rack that has room and would stay cool after taking one more job
            options = [r for r in racks
                       if r is not hot and r["jobs"] < CAPACITY and temp(r, r["jobs"] + 1) < SAFE_TARGET]
            if not options:
                break
            target = min(options, key=temp)
            hot["jobs"] -= 1
            target["jobs"] += 1
            moved_to[target["name"]] = moved_to.get(target["name"], 0) + 1
        if moved_to:
            where = ", ".join(f"{n} job{'s' if n > 1 else ''} to {r}" for r, n in moved_to.items())
            actions.append(f"Moved {where} from {hot['hall']} {hot['name']}. "
                           f"Temperature {before}°C → {temp(hot)}°C.")
        if temp(hot) > HOT_LIMIT:
            approvals.append({
                "rack": hot["name"],
                "text": f"{hot['hall']} {hot['name']} is still {temp(hot)}°C and no rack has room. "
                        f"Pause its lowest-priority jobs? (needs your OK)",
            })
        if hot["cooling_penalty"] > 0:
            actions.append(f"Opened a repair ticket: check cooling for {hot['hall']} {hot['name']}.")
    return racks, actions, approvals
