"""Topology loading and impact propagation.

The topology is a DAG: an edge means "`to` depends on `from`". Impact flows
downstream. Each dependency has a type that decides how a failing
dependency affects its dependent (see EFFECT), and dependencies can be
grouped for redundancy (`min` of N must be healthy).

`propagate()` turns each node's *own* condition (from the simulator) into an
*effective* condition (own + everything upstream), including a forecast:
the worst status the node will reach if nothing is done, and when.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEV = {"ok": 0, "at_risk": 1, "degraded": 2, "down": 3}
STATUSES = ["ok", "at_risk", "degraded", "down"]

# How a dependency's status maps onto its dependent, per edge type.
EFFECT: dict[str, dict[str, str]] = {
    "power": {"down": "down", "degraded": "at_risk", "at_risk": "at_risk"},
    "cooling": {"down": "at_risk", "degraded": "at_risk", "at_risk": "at_risk"},
    "network": {"down": "down", "degraded": "degraded", "at_risk": "at_risk"},
    "host": {"down": "down", "degraded": "degraded", "at_risk": "at_risk"},
    "storage_training": {"down": "down", "degraded": "degraded"},
    "storage_inference": {"down": "degraded", "degraded": "degraded"},
    "replication": {"down": "at_risk", "degraded": "at_risk"},
    "failover": {"down": "at_risk"},
}

# Thermal model (rack inlet temperature, °C, per simulated minute)
THERMAL_K = 0.055
THERMAL_LIMIT = 35.0
THERMAL_SHUTDOWN = 40.0
COOLING_EFF = {"ok": 1.0, "at_risk": 1.0, "degraded": 0.15, "down": 0.0}


def thermal_equilibrium(eff: float, load: float) -> float:
    return 22.0 + 4.0 * load + (1.0 - eff) * 24.0


def minutes_to_temp(t0: float, teq: float, target: float) -> Optional[float]:
    """Minutes for an exponential approach from t0 toward teq to cross target."""
    if t0 >= target:
        return 0.0
    if teq <= target:
        return None
    return math.log((teq - t0) / (teq - target)) / THERMAL_K


def worse(a: str, b: str) -> str:
    return a if SEV[a] >= SEV[b] else b


@dataclass
class Forecast:
    status: str
    eta: float  # simulated minutes from now
    reason: str

    def to_dict(self):
        return {"status": self.status, "eta": round(self.eta, 1), "reason": self.reason}


@dataclass
class Own:
    """A node's own condition, ignoring dependencies."""
    status: str = "ok"
    forecast: Optional[Forecast] = None
    reason: str = ""
    maintenance: bool = False


@dataclass
class Eff:
    status: str = "ok"
    forecast: Optional[Forecast] = None
    cause: Optional[str] = None  # root node causing the impact
    reason: str = ""

    def to_dict(self):
        return {
            "status": self.status,
            "forecast": self.forecast.to_dict() if self.forecast else None,
            "cause": self.cause,
            "reason": self.reason,
        }


@dataclass
class Dep:
    sources: list[str]
    to: str
    type: str
    min: int = 0  # 0 = every source required (no redundancy)
    label: str = ""
    dynamic: bool = False


@dataclass
class Topology:
    regions: list[dict]
    customers: dict[str, dict]
    nodes: dict[str, dict]
    static_deps: list[Dep]
    latency: dict[str, dict[str, int]]
    egress_cost_per_gb: float
    presets: list[dict]
    version: int = 1
    _order: list[str] = field(default_factory=list)
    _deps_into: dict[str, list[Dep]] = field(default_factory=dict)
    _children: dict[str, set[str]] = field(default_factory=dict)
    _parents: dict[str, set[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------ build
    @classmethod
    def load(cls, path: Path = DATA_DIR / "topology.yaml") -> "Topology":
        raw = yaml.safe_load(path.read_text())
        nodes: dict[str, dict] = {}
        for c in raw["components"]:
            nodes[c["id"]] = dict(c)
        for w in raw.get("workloads", []):
            n = dict(w)
            n["kind"] = "workload"
            n["wtype"] = n.pop("type")
            n["home_region"] = n["region"]
            nodes[n["id"]] = n
        deps: list[Dep] = []
        for d in raw.get("dependencies", []):
            sources = d["from"] if isinstance(d["from"], list) else [d["from"]]
            targets = d["to"] if isinstance(d["to"], list) else [d["to"]]
            for t in targets:
                deps.append(Dep(sources=list(sources), to=t, type=d["type"],
                                min=int(d.get("min", 0)), label=d.get("label", "")))
        for n in nodes.values():
            if n["kind"] == "gpu_node" and n.get("rack"):
                deps.append(Dep(sources=[n["rack"]], to=n["id"], type="host"))
        for d in deps:
            for s in d.sources + [d.to]:
                if s not in nodes:
                    raise ValueError(f"topology.yaml: unknown component '{s}'")
        topo = cls(
            regions=raw["regions"],
            customers={c["id"]: c for c in raw.get("customers", [])},
            nodes=nodes,
            static_deps=deps,
            latency=raw.get("region_latency_ms", {}),
            egress_cost_per_gb=float(raw.get("egress_cost_per_gb", 0.02)),
            presets=raw.get("incident_presets", []),
        )
        topo.rebuild()
        return topo

    def workload_deps(self) -> list[Dep]:
        out = []
        for n in self.nodes.values():
            if n["kind"] != "workload":
                continue
            out.append(Dep(sources=[n["host"]], to=n["id"], type="host", dynamic=True))
            if n.get("storage"):
                st = "storage_training" if n["wtype"] == "training" else "storage_inference"
                out.append(Dep(sources=[n["storage"]], to=n["id"], type=st, dynamic=True))
        return out

    def all_deps(self) -> list[Dep]:
        return self.static_deps + self.workload_deps()

    def rebuild(self):
        """Recompute adjacency + topological order (after a migration)."""
        deps = self.all_deps()
        self._deps_into = {nid: [] for nid in self.nodes}
        self._children = {nid: set() for nid in self.nodes}
        self._parents = {nid: set() for nid in self.nodes}
        for d in deps:
            self._deps_into[d.to].append(d)
            for s in d.sources:
                self._children[s].add(d.to)
                self._parents[d.to].add(s)
        indeg = {nid: len(self._parents[nid]) for nid in self.nodes}
        queue = [nid for nid, k in indeg.items() if k == 0]
        order = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for c in sorted(self._children[nid]):
                indeg[c] -= 1
                if indeg[c] == 0:
                    queue.append(c)
        # Any cycle members are appended last (shouldn't happen in a sane file)
        order += [nid for nid in self.nodes if nid not in order]
        self._order = order

    def bump(self):
        self.version += 1
        self.rebuild()

    # --------------------------------------------------------------- queries
    def descendants(self, nid: str) -> set[str]:
        seen, stack = set(), [nid]
        while stack:
            for c in self._children[stack.pop()]:
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen

    def ancestors(self, nid: str) -> set[str]:
        seen, stack = set(), [nid]
        while stack:
            for p in self._parents[stack.pop()]:
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return seen

    def region_latency(self, a: str, b: str) -> int:
        return int(self.latency.get(a, {}).get(b, 0 if a == b else 100))

    def gpu_used(self, gpu_id: str) -> int:
        return sum(n["gpus"] for n in self.nodes.values()
                   if n["kind"] == "workload" and n["host"] == gpu_id)

    def to_dict(self) -> dict:
        edges = []
        for i, d in enumerate(self.all_deps()):
            for s in d.sources:
                edges.append({
                    "id": f"e{i}-{s}-{d.to}",
                    "source": s,
                    "target": d.to,
                    "type": d.type.split("_")[0],
                    "redundant": len(d.sources) > 1,
                    "label": d.label,
                    "cross_region": self.nodes[s]["region"] != self.nodes[d.to]["region"],
                })
        nodes = []
        for n in self.nodes.values():
            item = copy.deepcopy(n)
            if n["kind"] == "gpu_node":
                item["gpus_used"] = self.gpu_used(n["id"])
            if n["kind"] == "workload":
                c = self.customers.get(n["customer"], {})
                item["customer_name"] = c.get("name", n["customer"])
                item["tier"] = c.get("tier", "silver")
            nodes.append(item)
        return {
            "version": self.version,
            "regions": self.regions,
            "customers": list(self.customers.values()),
            "nodes": nodes,
            "edges": edges,
            "presets": self.presets,
        }

    # ----------------------------------------------------------- propagation
    def propagate(self, own: dict[str, Own], metrics: dict[str, dict]) -> dict[str, Eff]:
        eff: dict[str, Eff] = {}
        for nid in self._order:
            node = self.nodes[nid]
            o = own.get(nid) or Own()
            status = o.status
            forecasts: list[tuple[Forecast, Optional[str]]] = []
            if o.forecast:
                forecasts.append((o.forecast, nid))
            cause = nid if (o.status != "ok" or o.forecast) else None
            reason = o.reason
            worst_dep_sev = 0

            for dep in self._deps_into[nid]:
                cur, fut, d_cause, d_reason = self._dep_effect(node, dep, eff, metrics)
                if SEV[cur] > SEV[status]:
                    status = cur
                if SEV[cur] > worst_dep_sev and (cause is None or SEV[cur] > SEV[o.status]):
                    worst_dep_sev = SEV[cur]
                    cause, reason = d_cause, d_reason
                if fut:
                    forecasts.append((fut, d_cause))

            fc = None
            fc_cause = None
            for f, c in forecasts:
                if SEV[f.status] <= SEV[status]:
                    continue
                if fc is None or f.eta < fc.eta - 0.01 or (abs(f.eta - fc.eta) < 0.01 and SEV[f.status] > SEV[fc.status]):
                    fc, fc_cause = f, c
            if cause is None and fc is not None:
                cause, reason = fc_cause, fc.reason
            eff[nid] = Eff(status=status, forecast=fc, cause=cause if (status != "ok" or fc) else None,
                           reason=reason if (status != "ok" or fc) else "")
        return eff

    def _dep_effect(self, node: dict, dep: Dep, eff: dict[str, Eff], metrics: dict[str, dict]):
        """Return (current status, forecast, cause, reason) imposed by one dependency."""
        kind = node["kind"]
        members = [(s, eff[s]) for s in dep.sources]

        # --- special case: UPS loses its input feed -> runs on battery
        if kind == "ups" and dep.type == "power":
            s, e = members[0]
            batt = metrics.get(node["id"], {}).get("battery_pct", 100.0)
            runtime = node.get("runtime_min", 15) * batt / 100.0
            if e.status == "down":
                return ("degraded", Forecast("down", runtime, f"{node['name']} battery exhausted"),
                        e.cause or s, f"on battery — {self.nodes[s]['name']} lost")
            if e.forecast and e.forecast.status == "down":
                return ("ok", Forecast("degraded", e.forecast.eta, "UPS switches to battery"), e.cause or s, "")
            return ("ok", None, None, "")

        # --- special case: CRAC loses chilled water -> cannot cool
        if kind == "crac" and dep.type == "cooling":
            s, e = members[0]
            mapping = {"down": "degraded", "degraded": "degraded", "at_risk": "at_risk"}
            cur = mapping.get(e.status, "ok")
            fut = None
            if e.forecast:
                fut = Forecast(mapping.get(e.forecast.status, "ok"), e.forecast.eta, e.forecast.reason)
                if fut.status == "ok":
                    fut = None
            return (cur, fut, (e.cause or s) if cur != "ok" or fut else None,
                    f"chilled water lost ({self.nodes[s]['name']})" if cur != "ok" else "")

        # --- special case: rack loses cooling -> thermal forecast
        if kind == "rack" and dep.type == "cooling":
            s, e = members[0]
            m = metrics.get(node["id"], {})
            t0 = m.get("inlet_c", 25.0)
            load = m.get("load", 0.8)

            def thermal(crac_status: str, delay: float):
                eff_c = COOLING_EFF[crac_status]
                if eff_c >= 1.0:
                    return None
                teq = thermal_equilibrium(eff_c, load)
                if t0 < THERMAL_LIMIT:
                    to_limit = minutes_to_temp(t0, teq, THERMAL_LIMIT)
                    if to_limit is None:
                        return None
                    return Forecast("degraded", delay + to_limit,
                                    f"reach thermal limit ({THERMAL_LIMIT:.0f}°C)")
                to_shut = minutes_to_temp(t0, teq, THERMAL_SHUTDOWN)
                if to_shut is None:
                    return None
                return Forecast("down", delay + to_shut,
                                f"thermal shutdown ({THERMAL_SHUTDOWN:.0f}°C)")

            cur = "at_risk" if COOLING_EFF[e.status] < 1.0 else "ok"
            fut = thermal(e.status, 0.0)
            if fut is None and e.forecast:
                fut = thermal(e.forecast.status, e.forecast.eta)
            return (cur, fut, (e.cause or s) if (cur != "ok" or fut) else None,
                    f"cooling lost ({self.nodes[s]['name']})" if cur != "ok" else "")

        etype = dep.type
        mapping = EFFECT.get(etype, EFFECT["host"])

        def mapped(st: str) -> str:
            return mapping.get(st, "ok") if st != "ok" else "ok"

        if len(members) == 1 or dep.min == 0:
            cur, fut, cause, reason = "ok", None, None, ""
            for s, e in members:
                m = mapped(e.status)
                if SEV[m] > SEV[cur]:
                    cur, cause = m, e.cause or s
                    reason = e.reason or f"{etype}: {self.nodes[s]['name']} {e.status}"
                if e.forecast:
                    fm = mapped(e.forecast.status)
                    if fm != "ok" and (fut is None or e.forecast.eta < fut.eta):
                        fut = Forecast(fm, e.forecast.eta, e.forecast.reason)
                        if cause is None:
                            cause = e.cause or s
            return cur, fut, cause, reason

        # --- redundant group (min of N must be functional)
        def group_result(statuses: list[str]) -> str:
            functional = sum(1 for st in statuses if SEV[st] <= SEV["at_risk"])
            if functional >= dep.min:
                lost = any(SEV[st] >= SEV["degraded"] for st in statuses)
                all_risky = all(st != "ok" for st in statuses)
                return "at_risk" if (lost or all_risky) else "ok"
            bad = [mapped(st) for st in statuses if SEV[st] >= SEV["degraded"]]
            res = "ok"
            for b in bad:
                res = worse(res, b)
            return res

        now = [e.status for _, e in members]
        cur = group_result(now)
        future = [(e.forecast.status if e.forecast else e.status) for _, e in members]
        fut_status = group_result(future)
        fut = None
        if SEV[fut_status] > SEV[cur]:
            etas = [e.forecast.eta for _, e in members if e.forecast]
            reasons = [e.forecast.reason for _, e in members if e.forecast]
            fut = Forecast(fut_status, max(etas), reasons[0])
        cause = None
        reason = ""
        for s, e in members:
            if e.status != "ok" or e.forecast:
                cause = e.cause or s
                if e.status != "ok":
                    reason = f"redundancy lost: {self.nodes[s]['name']} {e.status}"
                break
        if cur == "ok" and fut is None:
            cause, reason = None, ""
        return cur, fut, cause, reason


def compress_names(names: list[str]) -> str:
    """'Rack B4','Rack B5','Rack B6' -> 'Racks B4–B6'."""
    import re
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    parsed = []
    for n in names:
        m = re.match(r"^(.*?)([A-Za-z]?)(\d+)$", n)
        if not m:
            return ", ".join(names)
        parsed.append((m.group(1), m.group(2), int(m.group(3))))
    prefixes = {(p, l) for p, l, _ in parsed}
    if len(prefixes) != 1:
        return ", ".join(names)
    p, letter = prefixes.pop()
    nums = sorted(n for _, _, n in parsed)
    plural = p.strip() + "s " if p.strip() else ""
    if nums == list(range(nums[0], nums[-1] + 1)):
        return f"{plural}{letter}{nums[0]}–{letter}{nums[-1]}"
    return plural + ", ".join(f"{letter}{n}" for n in nums)
