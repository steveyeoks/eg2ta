"""eg2xml.py: the translation tau (paper Definitions 3.1-3.5, Tier 2 per section 3.4)
from fragment-shape EG JSON to UPPAAL 5 XML.

    python eg2xml.py models/eg/tandem_2.json [-o models/uppaal/tandem_2.xml]
    python eg2xml.py --all            # every models/eg/*.json -> models/uppaal/

Realization (plan section 4.2): fire actions are binary channels, sched actions are
broadcast channels (binary for Tier 2 edges, k > 1), chain locations are committed,
the priority filter is a `chan priority` declaration, branch sets are branchpoints,
seed edges are one-shot widgets started active, increments saturate at the bound.
Importable: load(path) -> eg dict, validate(eg), translate(eg) -> nta dict, emit(nta) -> str.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
EG_DIR = HERE / "models" / "eg"
XML_DIR = HERE / "models" / "uppaal"

RE_UPDATE = re.compile(r"^(\w+)\s*([+-])=\s*(\d+)$")
RE_ATOM = re.compile(r"^(\w+)\s*>=\s*(\d+)$")


# ------------------------------------------------------------------ load / validate

def load(path) -> dict:
    eg = json.loads(Path(path).read_text(encoding="utf-8"))
    validate(eg)
    return eg


def validate(eg: dict) -> None:
    """Structural checks for C2-C5 and the seed convention. C6 and Assumption 2.1
    are declared by the model, not checked (the paper says so)."""
    V = eg["vertices"]
    vars_ = eg["variables"]
    assert "Run" in V and not V["Run"], "Run vertex must exist with no updates (Def. 2.4)"
    ids = [e["id"] for e in eg["edges"]]
    assert len(ids) == len(set(ids)), "duplicate edge ids"
    for w, ups in V.items():
        for u in ups:
            m = RE_UPDATE.match(u)
            assert m and m.group(1) in vars_, f"C2: bad update '{u}' at {w}"
    for e in eg["edges"]:
        a, b = e["delay"]
        assert 0 <= a <= b, f"bad delay on {e['id']}"
        assert e["from"] in V and e["to"] in V, f"unknown vertex on {e['id']}"
        assert e["to"] != "Run", "nothing may target Run"
        guard = e.get("guard", [])
        if guard:
            assert (a, b) == (0, 0), f"C5: guarded edge {e['id']} must be zero-delay"
            dec = {RE_UPDATE.match(u).group(1): int(RE_UPDATE.match(u).group(3))
                   for u in V[e["to"]] if RE_UPDATE.match(u).group(2) == "-"}
            for atom in guard:
                m = RE_ATOM.match(atom)
                assert m and m.group(1) in vars_, f"C4: bad atom '{atom}' on {e['id']}"
                assert int(m.group(2)) >= 1, f"C4: threshold must be >= 1 in '{atom}'"
                assert dec.get(m.group(1), 0) >= int(m.group(2)), \
                    f"C3: {e['to']} must decrement {m.group(1)} by >= {m.group(2)} (edge {e['id']})"
    for w, br in eg.get("branches", {}).items():
        for bid in br["edges"]:
            e = next(x for x in eg["edges"] if x["id"] == bid)
            assert e["from"] == w and e["delay"] == [0, 0] and not e.get("guard"), \
                f"branch edge {bid} must be zero-delay and unguarded (Def. 2.11)"
    zd = {e["id"] for e in eg["edges"] if e["delay"] == [0, 0] and e["from"] != "Run"}
    assert set(eg["priority"]) == zd, "priority must list exactly the non-seed zero-delay edges"


# ------------------------------------------------------------------ translate

def _neg(guard):
    return " || ".join(f"{RE_ATOM.match(a).group(1)} < {RE_ATOM.match(a).group(2)}" for a in guard)


def _update_expr(u, vars_):
    v, op, d = RE_UPDATE.match(u).groups()
    if op == "+":
        K = vars_[v]["bound"]
        return f"{v} = {v} + {d} > {K} ? {K} : {v} + {d}"
    return f"{v} = {v} - {d}"


def translate(eg: dict, priority=None) -> dict:
    """Return the NTA as a plain dict: declarations, templates, system."""
    vars_ = eg["variables"]
    edges = eg["edges"]
    by_id = {e["id"]: e for e in edges}
    seed = [e for e in edges if e["from"] == "Run"]
    plain = [e for e in edges if e["from"] != "Run"]
    branch_of = {}  # branch edge id -> (vertex, weight)
    for w, br in eg.get("branches", {}).items():
        for bid, wt in zip(br["edges"], br["weights"]):
            branch_of[bid] = (w, wt)
    prio = priority or eg["priority"]

    # global declarations
    decl = [f"// tau({eg['name']}): EG -> NTA (Definitions 3.1 to 3.5)"]
    for v, spec in vars_.items():
        # optional "min" (default 0) widens the domain below zero so that a bound
        # violation becomes a reachable state with a trace instead of an abort
        decl.append(f"int[{spec.get('min', 0)},{spec['bound']}] {v} = {spec['init']};")
    bcast = [e["id"] for e in plain if e.get("k", 1) == 1]
    binary = [e["id"] for e in plain if e.get("k", 1) > 1]
    if bcast:
        decl.append("broadcast chan " + ", ".join(f"sched_{i}" for i in bcast) + ";")
    if binary:
        decl.append("chan " + ", ".join(f"sched_{i}" for i in binary) + ";")
    decl.append("chan " + ", ".join(f"fire_{e['id']}" for e in edges) + ";")
    low = [f"fire_{e['id']}" for e in edges if e["delay"] != [0, 0] or e["from"] == "Run"]
    bands = [", ".join(low)] + [f"fire_{i}" for i in reversed(prio)]
    decl.append("chan priority " + " < ".join(bands) + ";")

    templates = []

    def widget(e, copy=None):
        name = f"W_{e['id']}" + (f"_{copy}" if copy else "")
        a, b = e["delay"]
        guard = e.get("guard", [])
        locs = [dict(id="idle", init=True), dict(id="active", inv=f"x <= {b}")]
        trs = [dict(src="idle", dst="active", guard=" && ".join(guard), sync=f"sched_{e['id']}?", assign="x = 0")]
        if guard:
            trs.append(dict(src="idle", dst="idle", guard=_neg(guard), sync=f"sched_{e['id']}?"))
        trs.append(dict(src="active", dst="idle", guard=f"x >= {a}", sync=f"fire_{e['id']}!"))
        templates.append(dict(name=name, clock=True, locs=locs, trs=trs, bps=[]))

    for e in plain:
        k = e.get("k", 1)
        if k == 1:
            widget(e)
        else:
            for j in range(1, k + 1):
                widget(e, j)
    for e in seed:
        a, b = e["delay"]
        templates.append(dict(
            name=f"W_{e['id']}", clock=True,
            locs=[dict(id="active", init=True, inv=f"x <= {b}"), dict(id="done")],
            trs=[dict(src="active", dst="done", guard=f"x >= {a}", sync=f"fire_{e['id']}!")], bps=[]))

    # supervisor
    locs = [dict(id="wait", init=True)]
    trs = []
    bps = []
    for w, ups in eg["vertices"].items():
        if w == "Run":
            continue
        outs = [e for e in plain if e["from"] == w]
        chain = [e for e in outs if e["id"] not in branch_of]
        branch = [e for e in outs if e["id"] in branch_of]
        steps = len(chain) + (1 if branch else 0)
        names = [f"apply_{w}_{i}" for i in range(steps)]
        for nm in names:
            locs.append(dict(id=nm, committed=True))
        first = names[0] if names else "wait"
        assign = ", ".join(_update_expr(u, vars_) for u in ups)
        for e in edges:
            if e["to"] == w:
                trs.append(dict(src="wait", dst=first, sync=f"fire_{e['id']}?", assign=assign))
        for i, e in enumerate(chain):
            nxt = names[i + 1] if i + 1 < steps else "wait"
            trs.append(dict(src=names[i], dst=nxt, sync=f"sched_{e['id']}!"))
        if branch:
            bp = f"bp_{w}"
            bps.append(bp)
            trs.append(dict(src=names[-1], dst=bp))
            for e in branch:
                wt = branch_of[e["id"]][1]
                trs.append(dict(src=bp, dst="wait", sync=f"sched_{e['id']}!", prob=str(int(round(wt * 10)))))
    templates.append(dict(name="SU", clock=False, locs=locs, trs=trs, bps=bps))

    return dict(name=eg["name"], decl="\n".join(decl), templates=templates,
                system="system " + ", ".join(t["name"] for t in templates) + ";")


# ------------------------------------------------------------------ emit

def emit(nta: dict) -> str:
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           "<!DOCTYPE nta PUBLIC '-//Uppaal Team//DTD Flat System 1.5//EN' "
           "'http://www.it.uu.se/research/group/darts/uppaal/flat-1_5.dtd'>",
           "<nta>", f"  <declaration>{escape(nta['decl'])}</declaration>"]
    uid = 0
    for t in nta["templates"]:
        ids = {}
        out.append("  <template>")
        out.append(f"    <name>{t['name']}</name>")
        if t["clock"]:
            out.append("    <declaration>clock x;</declaration>")
        for n, loc in enumerate(t["locs"]):
            ids[loc["id"]] = f"id{uid}"; uid += 1
            x, y = 200 * (n % 6), 150 * (n // 6)
            out.append(f'    <location id="{ids[loc["id"]]}" x="{x}" y="{y}">')
            out.append(f'      <name x="{x-10}" y="{y-30}">{loc["id"]}</name>')
            if loc.get("inv"):
                out.append(f'      <label kind="invariant" x="{x-10}" y="{y+20}">{escape(loc["inv"])}</label>')
            if loc.get("committed"):
                out.append("      <committed/>")
            out.append("    </location>")
        for n, bp in enumerate(t["bps"]):
            ids[bp] = f"id{uid}"; uid += 1
            out.append(f'    <branchpoint id="{ids[bp]}" x="{200*n}" y="300"/>')
        init = next(l["id"] for l in t["locs"] if l.get("init"))
        out.append(f'    <init ref="{ids[init]}"/>')
        for tr in t["trs"]:
            out.append("    <transition>")
            out.append(f'      <source ref="{ids[tr["src"]]}"/>')
            out.append(f'      <target ref="{ids[tr["dst"]]}"/>')
            for kind, key in (("guard", "guard"), ("synchronisation", "sync"),
                              ("assignment", "assign"), ("probability", "prob")):
                if tr.get(key):
                    out.append(f'      <label kind="{kind}">{escape(tr[key])}</label>')
            if tr["src"] == tr["dst"]:
                out.append('      <nail x="-40" y="40"/>'); out.append('      <nail x="40" y="40"/>')
            out.append("    </transition>")
        out.append("  </template>")
    out.append(f"  <system>{nta['system']}</system>")
    out.append("</nta>")
    return "\n".join(out) + "\n"


def convert(src: Path, dst: Path, priority=None):
    eg = load(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(emit(translate(eg, priority)), encoding="utf-8")
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--priority", help="comma-separated zero-delay edge ids, highest first")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    prio = a.priority.split(",") if a.priority else None
    if a.all:
        for src in sorted(EG_DIR.glob("*.json")):
            print(convert(src, XML_DIR / (src.stem + ".xml")).name)
        return
    src = Path(a.src)
    dst = Path(a.out) if a.out else XML_DIR / (src.stem + ".xml")
    print(convert(src, dst, prio))


if __name__ == "__main__":
    main()
