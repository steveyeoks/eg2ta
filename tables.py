"""tables.py: results/*.csv + model counts -> tables/*.md and *.tex (paper Tables 5.2-5.4 and A.1).

    python tables.py            # the four paper tables (tandem models only)
    python tables.py --all      # also the three full tables over every model (extra material)

Reads, in this order, results/results_extra.csv (fork-join and feedback rows),
results/results_battery.csv (the tandem battery, the run of record) and
results/results_frontier.csv (tandem_4, tandem_5); a later file overrides an earlier
one per query_id. The merge is written to results/results.csv. Then:

  tables/table52_design.{md,tex}       the experimental design, expected verdicts from expected.json
  tables/table53_results.{md,tex}      verdict, fires, wall time, states explored, n = 1, 2, 3
  tables/table54_exploration.{md,tex}  A[] true on tandem_n, n = 1..5: states stored, time, memory
  tables/tableA1_models.{md,tex}       EG size, NTA size, zone graph for the models of Figure 5.1

With --all, also the previous full tables (every model, every query):
  tables/table51_models.{md,tex}, table52_results.{md,tex}, table53_frontier.{md,tex}
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import count_elements as ce

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
TAB = HERE / "tables"
EG_DIR = HERE / "models" / "eg"
XML_DIR = HERE / "models" / "uppaal"

# precedence: later files win per query_id
RESULT_FILES = ("results_extra.csv", "results_battery.csv", "results_frontier.csv")

PROBLEM = {"acc": "ACCESSIBILITY", "ord": "ORDERING", "nic": "NONINTERCHANGEABILITY",
           "stall": "STALLING", "term": "STALLING"}
TOPOLOGIES = ("tandem", "fork_join", "feedback")

# the models of Figure 5.1: panel -> model id per n
PANEL = {"a": "tandem_{n}", "b": "tandem_{n}_batch", "c": "tandem_{n}_batch_norestart"}
PANEL_D = "tandem_2_batch_shared_p1"


# ---------------------------------------------------------------- loading

def load_rows() -> dict:
    files = [RES / f for f in RESULT_FILES if (RES / f).exists()]
    if not files:
        raise SystemExit(f"tables.py: no results CSV in {RES} (expected one of {', '.join(RESULT_FILES)}); "
                         "run run.py first")
    stray = sorted(p.name for p in RES.glob("results_*.csv") if p.name not in RESULT_FILES)
    if stray:
        print(f"note: ignoring {', '.join(stray)} (not one of {', '.join(RESULT_FILES)})")
    rows = {}
    for f in files:
        with f.open(encoding="utf-8") as fh:
            n = 0
            for r in csv.DictReader(fh):
                rows[r["query_id"]] = r
                n += 1
        print(f"{f.name}: {n} rows")
    merged = sorted(rows.values(), key=lambda r: r["query_id"])
    with (RES / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(merged[0].keys()))
        w.writeheader(); w.writerows(merged)
    print(f"results.csv: {len(merged)} rows merged")
    return rows


def load_expected() -> dict:
    p = HERE / "expected.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ---------------------------------------------------------------- formatting

def fmt_time(r):
    if r["verdict"] == "TIMEOUT":
        return f">= {float(r['timeout_s']):.0f}"
    return f"{float(r['wall_s']):.2f}" if r["wall_s"] else ""


def fmt_mem(r):
    return f"{float(r['resident_mb']):.0f}" if r["resident_mb"] else ""


def fmt_wall(seconds: float) -> str:
    """0.06 s, 0.67 s, 33 s: two decimals under ten seconds, whole seconds above."""
    return f"{seconds:.2f} s" if seconds < 10 else f"{seconds:.0f} s"


# longer patterns first, so that E<> is matched before <>
_TEX_REPL = (("_", "\\_"), ("&&", "$\\wedge$"), ("E<>", "$\\exists\\Diamond$"), ("A[]", "$\\forall\\Box$"),
             ("<>", "$\\Diamond$"), ("-->", "$\\leadsto$"), (">=", "$\\ge$"), ("<=", "$\\le$"), ("==", "$=$"))


def tex_cell(text) -> str:
    """The write_table escaping, applied outside $...$ math; math segments pass through verbatim.
    Markdown code spans `...` become \\texttt{...}."""
    parts = str(text).replace("\\|", "|").split("$")
    for i in range(0, len(parts), 2):  # even indices are outside math
        segs = parts[i].split("`")
        parts[i] = "".join(f"\\texttt{{{seg}}}" if j % 2 else seg for j, seg in enumerate(segs))
        for a, b in _TEX_REPL:
            parts[i] = parts[i].replace(a, b)
    return "$".join(parts)


def write_table(name, header, body, caption):
    TAB.mkdir(exist_ok=True)
    md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    (TAB / f"{name}.md").write_text(f"**{caption}**\n\n" + "\n".join(md) + "\n", encoding="utf-8")
    tex = ["\\begin{tabular}{" + "l" * len(header) + "}", "\\toprule",
           " & ".join(tex_cell(h) for h in header) + " \\\\", "\\midrule"]
    tex += [" & ".join(tex_cell(c) for c in row) + " \\\\" for row in body]
    tex += ["\\bottomrule", "\\end{tabular}"]
    (TAB / f"{name}.tex").write_text("% generated by tables.py, do not edit\n% " + caption + "\n"
                                     + "\n".join(tex) + "\n", encoding="utf-8")
    print(f"{name}: {len(body)} rows")


# ---------------------------------------------------------------- paper tables (tandem)

def expected_of(expected, qids):
    """One verdict if every listed query expects the same, else 'qid: V' pairs; '?' if unknown."""
    vs = [expected.get(q, "?") for q in qids]
    if len(set(vs)) == 1:
        return vs[0]
    return ", ".join(f"{q}: {v}" for q, v in zip(qids, vs))


def table52_design(expected):
    ns = (1, 2, 3)
    acc = expected_of(expected, [f"tandem_{n}__acc" for n in ns])
    ord_p1 = ", ".join(expected.get(f"tandem_2_batch_shared_p1__ord_{p}", "?") for p in ("P1", "P2"))
    ord_p2 = ", ".join(expected.get(f"tandem_2_batch_shared_p2__ord_{p}", "?") for p in ("P1", "P2"))
    nic_b = expected_of(expected, [f"tandem_{n}_batch__nic" for n in ns])
    nic_c = expected_of(expected, [f"tandem_{n}_batch_norestart__nic" for n in ns])
    st_b = expected_of(expected, [f"tandem_{n}_batch__stall" for n in ns])
    st_c = expected_of(expected, [f"tandem_{n}_batch_norestart__stall" for n in ns])
    header = ["problem", "EG-TCTL", "UPPAAL", "model: expected"]
    body = [
        ["ACCESSIBILITY", "$\\exists\\Diamond\\, q_n = 2$", "`E<> (SU.wait && qn == 2)`",
         f"(a), $n = 1, 2, 3$: {acc}"],
        ["ORDERING", "$\\exists\\Diamond\\, P_1$, $\\exists\\Diamond\\, P_2$",
         "`E<> (SU.wait && P1)`, `E<> (SU.wait && P2)`",
         f"(d) under $\\succ_1$: {ord_p1}. Under $\\succ_2$: {ord_p2}"],
        ["NONINTERCHANGEABILITY",
         "$(q_1 \\ge 1 \\wedge a_1 \\ge 1) \\rightsquigarrow (q_1 = 0 \\vee a_1 = 0)$",
         "`(SU.wait && (q1 >= 1 && a1 >= 1)) --> (SU.wait && (q1 == 0 \\|\\| a1 == 0))`",
         f"(b): {nic_b}. (c): {nic_c}. $n = 1, 2, 3$"],
        ["STALLING", "$\\exists\\Diamond\\,(\\mathrm{FEL} = \\emptyset \\wedge \\mathrm{dep} < 3)$",
         "`E<> (SU.wait && idle && dep < 3)`",
         f"(b): {st_b}. (c): {st_c}. $n = 1, 2, 3$"],
    ]
    write_table("table52_design", header, body,
                "Table 5.2. The experimental design, one row per problem; the models are the panels of "
                "Figure 5.1 and the expected verdicts are those of expected.json.")


def result_cell(r) -> str:
    """'SAT, 13 fires, 0.06 s, 38 states', the fires field omitted without a trace."""
    if r is None:
        return ""
    parts = [r["verdict"]]
    if r["witness_len"]:
        parts.append(f"{r['witness_len']} fires")
    if r["verdict"] == "TIMEOUT":
        parts.append(f">= {float(r['timeout_s']):.0f} s")
    elif r["wall_s"]:
        parts.append(f"{float(r['wall_s']):.2f} s")
    if r["states_explored"]:
        parts.append(f"{r['states_explored']} states")
    return ", ".join(parts)


def table53_results(rows):
    ns = (1, 2, 3)
    spec = [  # (row label, query id pattern with {n}, sizes at which it is asked)
        ("ACCESSIBILITY (a)", "tandem_{n}__acc", ns),
        ("ORDERING (d), $\\succ_1$, $P_1$", "tandem_2_batch_shared_p1__ord_P1", (2,)),
        ("ORDERING (d), $\\succ_1$, $P_2$", "tandem_2_batch_shared_p1__ord_P2", (2,)),
        ("ORDERING (d), $\\succ_2$, $P_1$", "tandem_2_batch_shared_p2__ord_P1", (2,)),
        ("ORDERING (d), $\\succ_2$, $P_2$", "tandem_2_batch_shared_p2__ord_P2", (2,)),
        ("NONINTERCHANGEABILITY (b)", "tandem_{n}_batch__nic", ns),
        ("NONINTERCHANGEABILITY (c)", "tandem_{n}_batch_norestart__nic", ns),
        ("STALLING (b)", "tandem_{n}_batch__stall", ns),
        ("STALLING (c)", "tandem_{n}_batch_norestart__stall", ns),
    ]
    header = ["problem, model"] + [f"$n = {n}$" for n in ns]
    body = []
    for label, pat, asked in spec:
        body.append([label] + [result_cell(rows.get(pat.format(n=n))) if n in asked else "" for n in ns])
    write_table("table53_results", header, body,
                "Table 5.3. Results for the rows of Table 5.2, one row per model and one run per cell: "
                "verdict, witness length in fire actions where a trace exists, wall time, states explored. "
                "ORDERING is asked at n = 2.")


def table54_exploration(rows):
    ns = (1, 2, 3, 4, 5)
    states, wall, mem = ["states stored"], ["wall time"], ["resident memory"]
    for n in ns:
        r = rows.get(f"tandem_{n}__zone") or rows.get(f"tandem_{n}__frontier")
        if r is None:
            states.append(""); wall.append(""); mem.append("")
        elif r["verdict"] == "TIMEOUT":
            states.append("timeout"); wall.append(f"{float(r['timeout_s']):.0f} s"); mem.append("")
        else:
            states.append(r["states_stored"])
            wall.append(fmt_wall(float(r["wall_s"])) if r["wall_s"] else "")
            mem.append(f"{fmt_mem(r)} MB" if r["resident_mb"] else "")
    write_table("table54_exploration", ["$n$"] + [str(n) for n in ns], [states, wall, mem],
                "Table 5.4. Exhaustive exploration of model (a) by size, A[] true on the tandem n queue; "
                "the timeout run was stopped at the stated budget.")


def tableA1_models(rows):
    header = ["model", "$\\lvert V \\rvert$", "timed", "zero", "vars", "$\\prod (K_j{+}1)$",
              "automata", "locations", "transitions", "clocks", "channels", "zone states", "time (s)", "MB"]
    items = [(f"({p}) $n = {n}$", PANEL[p].format(n=n)) for p in "abc" for n in (1, 2, 3)]
    items.append(("(d)", PANEL_D))
    body = []
    for label, m in items:
        z = rows.get(f"{m}__zone")
        eg = ce.count_eg(EG_DIR / f"{m}.json"); nta = ce.count_xml(XML_DIR / f"{m}.xml")
        body.append([label, eg["vertices"], eg["timed_edges"], eg["zero_edges"], eg["variables"], eg["valuations"],
                     nta["automata"], nta["locations"], nta["transitions"], nta["clocks"], nta["channels"],
                     z["states_stored"] if z else "", fmt_time(z) if z else "", fmt_mem(z) if z else ""])
    write_table("tableA1_models", header, body,
                "Table A.1. The models of Figure 5.1: EG size (vertices without Run; timed and zero-delay edges "
                "including the seed edges; state variables; product of their ranges), NTA size, and the "
                "exploration of the whole reachable state space (A[] true: states stored, wall time, resident "
                "memory). Row (d) is the shared-server tandem-2 under the first order.")


# ---------------------------------------------------------------- full tables (--all, every model)

def table51_all(rows):
    header = ["model", "|V|", "timed", "zero", "vars", "valuations",
              "automata", "locations", "transitions", "clocks", "channels", "zone states", "time s", "MB"]
    body = []
    for src in sorted(EG_DIR.glob("*.json")):
        m = src.stem
        z = rows.get(f"{m}__zone")
        if not z:
            continue
        eg = ce.count_eg(src); nta = ce.count_xml(XML_DIR / f"{m}.xml")
        body.append([m, eg["vertices"], eg["timed_edges"], eg["zero_edges"], eg["variables"], eg["valuations"],
                     nta["automata"], nta["locations"], nta["transitions"], nta["clocks"], nta["channels"],
                     z["states_stored"], fmt_time(z), fmt_mem(z)])
    write_table("table51_models", header, body,
                "All models (extra material): EG size (vertices without Run; timed edges include timed seed "
                "edges), NTA size, and the zone graph of A[] true (states stored, wall time, resident memory).")


def table52_all(rows):
    header = ["problem", "model", "query", "expected", "verdict", "witness", "time s", "states"]
    body = []
    for qid, r in sorted(rows.items()):
        label = qid.split("__")[1]
        key = label.split("_")[0]
        if key not in PROBLEM:
            continue
        body.append([PROBLEM[key], r["model"], f"`{r['query']}`", r["expected"], r["verdict"],
                     r["witness_len"], fmt_time(r), r["states_explored"]])
    write_table("table52_results", header, body,
                "All models (extra material): the four Jacobson-Yucesan problems on every model: expectation, "
                "verdict, witness length (fires), wall time, states explored.")


def table53_all(rows):
    header = ["topology", "n", "verdict", "states stored", "time s", "MB"]
    body = []
    for t in TOPOLOGIES:
        for n in (1, 2, 3, 4, 5):
            r = rows.get(f"{t}_{n}__zone") or rows.get(f"{t}_{n}__frontier")
            if r:
                body.append([t, n, r["verdict"], r["states_stored"], fmt_time(r), fmt_mem(r)])
    write_table("table53_frontier", header, body,
                "All topologies (extra material): exhaustive exploration (A[] true) per topology and size "
                "at capacity 1; TIMEOUT rows are censored at the stated budget.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true",
                    help="also write the full tables over every model (table51_models, table52_results, "
                         "table53_frontier)")
    a = ap.parse_args()
    rows = load_rows()
    table52_design(load_expected())
    table53_results(rows)
    table54_exploration(rows)
    tableA1_models(rows)
    if a.all:
        table51_all(rows); table52_all(rows); table53_all(rows)


if __name__ == "__main__":
    main()
