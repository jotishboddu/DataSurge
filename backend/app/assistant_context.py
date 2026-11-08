"""Compact, explicitly partial context for interactive questions."""


def compact_context(state, topology):
    def select(row, fields):
        return {key: row[key] for key in fields if key in row}
    return {
        "scope": "Current components and dependencies; up to 12 open incidents, 10 migrations, and 8 recent events. Older history and full handoffs omitted.",
        "clock": state["clock"], "stats": state["stats"],
        "components": [
            {**select(node, ("id", "name", "kind", "region", "host")),
             **select(state["nodes"].get(node["id"], {}), ("status", "reason", "forecast"))}
            for node in topology["nodes"]
        ],
        "dependencies": [select(edge, ("source", "target", "type")) for edge in topology["edges"]],
        "incidents": [select(row, ("id", "title", "priority", "status", "root", "assignee"))
                      for row in state["incidents"] if row["status"] != "resolved"][:12],
        "migrations": state["migrations"][:10],
        "recent_events": [select(row, ("time", "kind", "message")) for row in state["timeline"][-8:]],
    }
