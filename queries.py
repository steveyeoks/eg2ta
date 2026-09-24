"""queries.py: write queries/<model>__<label>.q and expected.json for the whole design
(plan sections 2, 3.1, 3.3). Every row carries a hand-derived expected verdict.

Labels: acc_* ACCESSIBILITY, ord_* ORDERING, nic_* NONINTERCHANGEABILITY,
stall_* STALLING, cost / zone the full-exploration rows, frontier the n = 4, 5 probes.
"""
from __future__ import annotations

import json
from pathlib import Path

import eg2xml

HERE = Path(__file__).resolve().parent
QDIR = HERE / "queries"
EG_DIR = HERE / "models" / "eg"

ROWS = []  # (model, label, comment, formula, expected)


def row(model, label, comment, formula, expected):
    ROWS.append((model, label, comment, formula, expected))


def fel_empty(model):
    """Every widget idle (seed widgets: done): the empty FEL at a rest state (Obs. 3.1)."""
    nta = eg2xml.translate(eg2xml.load(EG_DIR / f"{model}.json"))
    terms = []
    for t in nta["templates"]:
        if t["name"] == "SU":
            continue
        locs = {l["id"] for l in t["locs"]}
        terms.append(f"{t['name']}.{'done' if 'done' in locs else 'idle'}")
    return " && ".join(terms)


def rest(p):
    return f"E<> (SU.wait && {p})"


def leads(phi, psi):
    return f"(SU.wait && ({phi})) --> (SU.wait && ({psi}))"


def work_conserving(stations):
    phi = " || ".join(f"q{i} >= 1 && a{i} >= 1" for i in stations)
    return leads(phi, f"!({phi})")


def main():
    # ---------------- ACCESSIBILITY (HOLDS rows, one per battery model)
    for n in (1, 2, 3):
        row(f"tandem_{n}", "acc", f"two waiting at station {n}", rest(f"q{n} == 2"), "SAT")
        row(f"fork_join_{n}", "acc", "two waiting at branch 1", rest("q1 == 2"), "SAT")
        row(f"feedback_{n}", "acc", f"two waiting at station {n}", rest(f"q{n} == 2"), "SAT")
    # Tier 2 sanity: capacity questions on the replicated network
    row("tandem_2_c2", "acc_busy", "both servers of station 1 busy", rest("a1 == 0"), "SAT")
    row("tandem_2_c2", "acc_queue", "a queue forms at station 1 (never: two servers absorb the unit-box arrivals)",
        rest("q1 == 2"), "UNSAT")
    row("tandem_2_c5", "acc_two", "two of five servers busy", rest("a1 == 3"), "SAT")
    row("tandem_2_c5", "acc_all", "all five servers busy (never)", rest("a1 == 0"), "UNSAT")

    # ---------------- ORDERING
    # base n = 2 models under the declared and the reversed zero-delay priority: same verdicts
    for base, preds in (("tandem_2", ["q2 == 2", "q1 >= 2 && q2 >= 1"]),
                        ("fork_join_2", ["q1 == 2", "p1 >= 1 && q2 >= 1"]),
                        ("feedback_2", ["q2 == 2", "q1 >= 2 && q2 >= 1"])):
        for k, p in enumerate(preds, 1):
            for suffix in ("", "_alt"):
                row(base + suffix, f"ord_P{k}", f"order control predicate {k}", rest(p), "SAT")
    # shared server with dispatch vertices: the priority order decides the outcome
    P1 = "q1 == 0 && s1 == 1 && q2 == 1 && s2 == 0"   # station 1 won
    P2 = "q1 == 1 && s1 == 0 && q2 == 0 && s2 == 1"   # station 2 won
    row("tandem_2_batch_shared_p1", "ord_P1", "station 1 won the dispatch", rest(P1), "SAT")
    row("tandem_2_batch_shared_p1", "ord_P2", "station 2 won the dispatch", rest(P2), "UNSAT")
    row("tandem_2_batch_shared_p2", "ord_P1", "station 1 won the dispatch", rest(P1), "UNSAT")
    row("tandem_2_batch_shared_p2", "ord_P2", "station 2 won the dispatch", rest(P2), "SAT")
    row("tandem_2_batch_shared_p3", "ord_over", "both checks before either start: server allocated twice",
        rest("s1 == 1 && s2 == 1"), "RANGE")
    row("tandem_2_batch_shared_p3_wide", "ord_over", "same, r widened to [-1,1] for the trace",
        "E<> (r < 0)", "SAT")

    # ---------------- NONINTERCHANGEABILITY (leads-to on the batch models)
    wc1 = leads("q1 >= 1 && a1 >= 1", "q1 == 0 || a1 == 0")
    row("tandem_2_batch", "nic", "work conservation at station 1", wc1, "SAT")
    row("tandem_2_batch_norestart", "nic", "work conservation at station 1 (Finish1->Start1 missing)", wc1, "UNSAT")
    for n in (1, 3):
        row(f"tandem_{n}_batch", "nic", "work conservation at station 1", wc1, "SAT")
        row(f"tandem_{n}_batch_norestart", "nic", "work conservation at station 1 (Finish1->Start1 missing)", wc1, "UNSAT")
    row("tandem_2_batch_permuted", "nic", "work conservation at station 1 (permuted control)", wc1, "SAT")
    jn = leads("p1 >= 1 && p2 >= 1", "p1 == 0 || p2 == 0")
    row("fork_join_2_batch", "nic", "parts present are joined", jn, "SAT")
    row("fork_join_2_batch_nojoin", "nic", "parts present are joined (Finish2->Join missing)", jn, "UNSAT")
    row("fork_join_2_batch_permuted", "nic", "parts present are joined (permuted control)", jn, "SAT")
    wc2 = leads("q2 >= 1 && a2 >= 1", "q2 == 0 || a2 == 0")
    row("feedback_2_batch", "nic", "work conservation at station 2", wc2, "SAT")
    row("feedback_2_batch_nodepartcheck", "nic", "work conservation at station 2 (Depart->Start2 missing)", wc2, "UNSAT")
    row("feedback_2_batch_permuted", "nic", "work conservation at station 2 (permuted control)", wc2, "SAT")

    # ---------------- STALLING
    for base in ("tandem_2", "fork_join_2", "feedback_2"):
        row(base, "stall", "open model: the FEL never empties", rest(fel_empty(base)), "UNSAT")
    for base, bug in (("tandem_2_batch", "tandem_2_batch_norestart"),
                      ("tandem_1_batch", "tandem_1_batch_norestart"),
                      ("tandem_3_batch", "tandem_3_batch_norestart"),
                      ("fork_join_2_batch", "fork_join_2_batch_nojoin"),
                      ("feedback_2_batch", "feedback_2_batch_nodepartcheck")):
        row(base, "stall", "batch: FEL empty before all 3 departed (never)", rest(fel_empty(base) + " && dep < 3"), "UNSAT")
        row(base, "term", "batch: FEL empty with all 3 departed (normal termination)", rest(fel_empty(base) + " && dep == 3"), "SAT")
        row(bug, "stall", "batch bug: FEL empty with work left", rest(fel_empty(bug) + " && dep < 3"), "SAT")

    # ---------------- cost rows (full exploration) and frontier probes
    for n in (1, 2, 3):
        st = list(range(1, n + 1))
        for base in (f"tandem_{n}", f"fork_join_{n}", f"feedback_{n}"):
            row(base, "cost", "work conservation at every station", work_conserving(st), "SAT")
            row(base, "zone", "full zone graph", "A[] true", "SAT")
    for c in ("c2", "c5"):
        row(f"tandem_2_{c}", "cost", "work conservation at every station", work_conserving([1, 2]), "SAT")
        row(f"tandem_2_{c}", "zone", "full zone graph", "A[] true", "SAT")
    # zone rows for the variants too, so Table 5.1 lists every battery model
    done = {(m, l) for m, l, *_ in ROWS}
    for src in sorted(EG_DIR.glob("*.json")):
        m = src.stem
        if m[-2:] in ("_4", "_5") or (m, "zone") in done:
            continue
        exp = "RANGE" if m == "tandem_2_batch_shared_p3" else "SAT"
        row(m, "zone", "full zone graph", "A[] true", exp)
    for n in (4, 5):
        for base in (f"tandem_{n}", f"fork_join_{n}", f"feedback_{n}"):
            row(base, "frontier", "frontier probe, 600 s", "A[] true", "")

    # ---------------- write
    QDIR.mkdir(exist_ok=True)
    for old in QDIR.glob("*.q"):
        old.unlink()
    expected = {}
    for model, label, comment, formula, exp in ROWS:
        qid = f"{model}__{label}"
        (QDIR / f"{qid}.q").write_text(f"// {comment}\n{formula}\n", encoding="utf-8")
        if exp:
            expected[qid] = exp
    (HERE / "expected.json").write_text(json.dumps(expected, indent=1), encoding="utf-8")
    print(f"{len(ROWS)} queries, {len(expected)} with expected verdicts")


if __name__ == "__main__":
    main()
