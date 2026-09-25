"""gen_models.py: write the fragment-shape EG JSON files into models/eg/.

Topologies (plan §1.2): tandem_n, fork_join_n, feedback_n, with the unit-box delays
arrival [4,6], service [3,5], queue bound K = 5, capacity 1 (Tier 1) unless stated.
Variants (plan §2, §3.1): batch (N seed arrivals, no self-loop, departure counter),
norestart / nojoin / nodepartcheck (one edge deleted), permuted (edge order and
commuting priorities changed), shared (one server pool r, in-service counters s_i),
c2 / c5 (Tier 2, service edge k = c).

JSON shape:
  name, variables {v: {init, bound}}, vertices {w: [update, ...]},
  edges [{id, from, to, delay: [a, b], guard: [atom, ...], k}],
  branches {w: {edges: [ids], weights: [w, ...]}},
  priority [ids of zero-delay edges, highest first]
Updates are "v += d" or "v -= d"; guard atoms are "v >= c". Edges from "Run" are seed edges.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "models" / "eg"

ARR = [4, 6]
SVC = [3, 5]
K = 5
BATCH_TIMES = [0, 4, 8]


class EG:
    def __init__(self, name):
        self.name = name
        self.variables = {}
        self.vertices = {"Run": []}
        self.edges = []
        self.branches = {}
        self._n = 0

    def var(self, name, init, bound, min=None):
        self.variables[name] = {"init": init, "bound": bound}
        if min is not None:  # optional lower bound, default 0 (see eg2xml.py)
            self.variables[name]["min"] = min

    def vertex(self, name, *updates):
        self.vertices[name] = list(updates)

    def edge(self, src, dst, delay, guard=(), k=None, eid=None):
        self._n += 1
        e = {"id": eid or f"e{self._n}", "from": src, "to": dst, "delay": list(delay)}
        if guard:
            e["guard"] = list(guard)
        if k:
            e["k"] = k
        self.edges.append(e)
        return e["id"]

    def delete(self, src, dst):
        before = len(self.edges)
        self.edges = [e for e in self.edges if not (e["from"] == src and e["to"] == dst)]
        assert len(self.edges) == before - 1, f"expected one edge {src}->{dst}"

    def zero_delay_ids(self):
        return [e["id"] for e in self.edges if e["delay"] == [0, 0] and e["from"] != "Run"]

    def to_json(self, priority=None):
        return {
            "name": self.name,
            "variables": self.variables,
            "vertices": self.vertices,
            "edges": self.edges,
            "branches": self.branches,
            "priority": priority or self.zero_delay_ids(),
        }


def start_check(a, q=None):
    return [f"{q} >= 1", f"{a} >= 1"] if q else [f"{a} >= 1"]


# ---------------------------------------------------------------- arrivals

def arrivals(m, batch):
    """Seed edge(s) into Arrive; open models add the self-loop."""
    if batch:
        for i, t in enumerate(BATCH_TIMES[:batch]):
            m.edge("Run", "Arrive", [t, t], eid=f"e0{'abc'[i]}")
        m.var("dep", 0, batch)
    else:
        m.edge("Run", "Arrive", [0, 0], eid="e0")
        m.edge("Arrive", "Arrive", ARR)


# ---------------------------------------------------------------- tandem

def tandem(n, batch=0, cap=1, name=None):
    m = EG(name or f"tandem_{n}")
    for i in range(1, n + 1):
        m.var(f"q{i}", 0, K)
        m.var(f"a{i}", cap, cap)
    m.vertex("Arrive", "q1 += 1")
    for i in range(1, n + 1):
        m.vertex(f"Start{i}", f"q{i} -= 1", f"a{i} -= 1")
        fin = [f"a{i} += 1"] + ([f"q{i+1} += 1"] if i < n else (["dep += 1"] if batch else []))
        m.vertex(f"Finish{i}", *fin)
    arrivals(m, batch)
    m.edge("Arrive", "Start1", [0, 0], start_check("a1"))
    for i in range(1, n + 1):
        m.edge(f"Start{i}", f"Finish{i}", SVC, k=cap if cap > 1 else None)
        m.edge(f"Finish{i}", f"Start{i}", [0, 0], start_check(f"a{i}", f"q{i}"))
        if i < n:
            m.edge(f"Finish{i}", f"Start{i+1}", [0, 0], start_check(f"a{i+1}"))
    return m


def tandem_shared(batch=2, r_min=None):
    """tandem_2 with one server pool r, in-service counters s1, s2, and one dispatch
    vertex Check_i per station (plan §2.2). Guards are evaluated when an edge is
    scheduled (Def. 2.6 step 3), so a freed server must be offered to the two
    stations through separate Check vertices: the priority order among the Check
    and Start edges then decides which station gets it, or whether both do.
    Returns the model and the edge ids (check1, start1, check2, start2) of the
    Finish_1 dispatch, from which the three priority orders are built.
    r_min widens the domain of r below zero (the _wide variant)."""
    m = EG("tandem_2_batch_shared")
    m.var("q1", 0, K); m.var("q2", 0, K)
    m.var("r", 1, 1, min=r_min)
    m.var("s1", 0, 1); m.var("s2", 0, 1)
    m.var("dep", 0, batch)
    m.vertex("Arrive", "q1 += 1")
    m.vertex("Check1"); m.vertex("Check2")
    m.vertex("Start1", "q1 -= 1", "r -= 1", "s1 += 1")
    m.vertex("Finish1", "r += 1", "s1 -= 1", "q2 += 1")
    m.vertex("Start2", "q2 -= 1", "r -= 1", "s2 += 1")
    m.vertex("Finish2", "r += 1", "s2 -= 1", "dep += 1")
    m.edge("Run", "Arrive", [0, 0], eid="e0a")
    m.edge("Run", "Arrive", [1, 1], eid="e0b")
    arr = m.edge("Arrive", "Start1", [0, 0], ["r >= 1"])
    m.edge("Start1", "Finish1", SVC)
    m.edge("Start2", "Finish2", SVC)
    c1 = m.edge("Finish1", "Check1", [0, 0]); c2 = m.edge("Finish1", "Check2", [0, 0])
    d1 = m.edge("Finish2", "Check1", [0, 0]); d2 = m.edge("Finish2", "Check2", [0, 0])
    s1 = m.edge("Check1", "Start1", [0, 0], ["q1 >= 1", "r >= 1"])
    s2 = m.edge("Check2", "Start2", [0, 0], ["q2 >= 1", "r >= 1"])
    orders = {
        # station 1 first: Check1 runs, Start1 fires before Check2 looks, Check2 skips
        "p1": [s1, c1, d1, c2, d2, s2, arr],
        # station 2 first: the mirror image
        "p2": [s2, c2, d2, c1, d1, s1, arr],
        # both checks before either start: both see r = 1, both Starts fire, r -> -1
        "p3": [c1, d1, c2, d2, s1, s2, arr],
    }
    return m, orders


# ---------------------------------------------------------------- fork-join

def fork_join(n, batch=0, name=None):
    m = EG(name or f"fork_join_{n}")
    for i in range(1, n + 1):
        m.var(f"q{i}", 0, K); m.var(f"a{i}", 1, 1); m.var(f"p{i}", 0, K)
    m.vertex("Arrive")
    m.vertex("Fork", *[f"q{i} += 1" for i in range(1, n + 1)])
    for i in range(1, n + 1):
        m.vertex(f"Start{i}", f"q{i} -= 1", f"a{i} -= 1")
        m.vertex(f"Finish{i}", f"a{i} += 1", f"p{i} += 1")
    m.vertex("Join", *[f"p{i} -= 1" for i in range(1, n + 1)], *(["dep += 1"] if batch else []))
    arrivals(m, batch)
    m.edge("Arrive", "Fork", [0, 0])
    join_guard = [f"p{i} >= 1" for i in range(1, n + 1)]
    for i in range(1, n + 1):
        m.edge("Fork", f"Start{i}", [0, 0], start_check(f"a{i}", f"q{i}"))
    for i in range(1, n + 1):
        m.edge(f"Start{i}", f"Finish{i}", SVC)
        m.edge(f"Finish{i}", f"Start{i}", [0, 0], start_check(f"a{i}", f"q{i}"))
        m.edge(f"Finish{i}", "Join", [0, 0], join_guard)
    return m


# ---------------------------------------------------------------- feedback

def feedback(n, batch=0, name=None):
    m = EG(name or f"feedback_{n}")
    for i in range(1, n + 1):
        m.var(f"q{i}", 0, K); m.var(f"a{i}", 1, 1)
    m.vertex("Arrive", "q1 += 1")
    for i in range(1, n + 1):
        m.vertex(f"Start{i}", f"q{i} -= 1", f"a{i} -= 1")
        m.vertex(f"Finish{i}", f"a{i} += 1", *([f"q{i+1} += 1"] if i < n else []))
    m.vertex("Requeue", "q1 += 1")
    m.vertex("Depart", *(["dep += 1"] if batch else []))
    arrivals(m, batch)
    m.edge("Arrive", "Start1", [0, 0], start_check("a1"))
    for i in range(1, n + 1):
        m.edge(f"Start{i}", f"Finish{i}", SVC)
        m.edge(f"Finish{i}", f"Start{i}", [0, 0], start_check(f"a{i}", f"q{i}"))
        if i < n:
            m.edge(f"Finish{i}", f"Start{i+1}", [0, 0], start_check(f"a{i+1}"))
    m.delete(f"Finish{n}", f"Start{n}")  # Finish_n is the branch vertex: its checks ride the branches
    b1 = m.edge(f"Finish{n}", "Requeue", [0, 0])
    b2 = m.edge(f"Finish{n}", "Depart", [0, 0])
    m.branches[f"Finish{n}"] = {"edges": [b1, b2], "weights": [0.3, 0.7]}
    m.edge("Requeue", "Start1", [0, 0], start_check("a1", "q1"))
    if n > 1:
        m.edge("Requeue", f"Start{n}", [0, 0], start_check(f"a{n}", f"q{n}"))
    m.edge("Depart", f"Start{n}", [0, 0], start_check(f"a{n}", f"q{n}"))
    return m


# ---------------------------------------------------------------- variants

def permuted(m, name):
    """Same model, edges listed in reverse, zero-delay priorities reversed."""
    p = EG(name)
    p.variables = dict(m.variables); p.vertices = dict(m.vertices)
    p.edges = list(reversed(m.edges)); p.branches = dict(m.branches)
    return p, list(reversed(m.zero_delay_ids()))


def write(m, priority=None, name=None):
    d = m.to_json(priority)
    if name:
        d["name"] = name
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{d['name']}.json"
    path.write_text(json.dumps(d, indent=1), encoding="utf-8")
    print(path.name)


def main():
    # base models, n = 1..5 (n = 4, 5 for the frontier probe only)
    for n in (1, 2, 3, 4, 5):
        write(tandem(n)); write(fork_join(n)); write(feedback(n))
    # ORDERING controls: the n = 2 base models under the reversed zero-delay priority
    for f in (tandem, fork_join, feedback):
        m = f(2)
        write(m, list(reversed(m.zero_delay_ids())), m.name + "_alt")
    # Tier 2
    write(tandem(2, cap=2, name="tandem_2_c2"))
    write(tandem(2, cap=5, name="tandem_2_c5"))
    # batch models and bug files
    write(tandem(2, batch=3, name="tandem_2_batch"))
    m = tandem(2, batch=3, name="tandem_2_batch_norestart"); m.delete("Finish1", "Start1"); write(m)
    write(tandem(1, batch=3, name="tandem_1_batch"))
    m = tandem(1, batch=3, name="tandem_1_batch_norestart"); m.delete("Finish1", "Start1"); write(m)
    write(tandem(3, batch=3, name="tandem_3_batch"))
    m = tandem(3, batch=3, name="tandem_3_batch_norestart"); m.delete("Finish1", "Start1"); write(m)
    p, prio = permuted(tandem(2, batch=3), "tandem_2_batch_permuted"); write(p, prio)
    write(fork_join(2, batch=3, name="fork_join_2_batch"))
    m = fork_join(2, batch=3, name="fork_join_2_batch_nojoin"); m.delete("Finish2", "Join"); write(m)
    p, prio = permuted(fork_join(2, batch=3), "fork_join_2_batch_permuted"); write(p, prio)
    write(feedback(2, batch=3, name="feedback_2_batch"))
    m = feedback(2, batch=3, name="feedback_2_batch_nodepartcheck"); m.delete("Depart", "Start2"); write(m)
    p, prio = permuted(feedback(2, batch=3), "feedback_2_batch_permuted"); write(p, prio)
    # ORDERING: shared server with dispatch vertices, three priority orders
    m, orders = tandem_shared()
    for tag, prio in orders.items():
        write(m, prio, f"tandem_2_batch_shared_{tag}")
    # p3 again with r widened to [-1,1]: verifyta prints no trace on a range abort,
    # so the witnessing sequence comes from E<> r < 0 on this variant
    m, orders = tandem_shared(r_min=-1)
    write(m, orders["p3"], "tandem_2_batch_shared_p3_wide")


if __name__ == "__main__":
    main()
