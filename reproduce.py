"""reproduce.py: one command for the paper's results.

    python3 reproduce.py                 # no UPPAAL needed: merge the recorded runs, write the tables,
                                         # print the Section 5.5 numbers, and check every number the
                                         # paper states against the recorded runs (PASS/FAIL per claim)
    python3 reproduce.py --smoke         # installation check: one query with UPPAAL, about one second
    python3 reproduce.py --rerun         # rerun every query of the paper with UPPAAL (about 12 minutes,
                                         # 10 of them the timeout row), then check the fresh results;
                                         # add --skip-timeout to leave out the n = 5 row (under 1 minute)

The claims are the numbers printed in the paper: the expected verdicts of Table 1, the verdicts,
witness lengths and states explored of Section 5.5, and the five exploration rows. On the recorded
runs every claim must match exactly. On a rerun, verdicts and witness lengths must match; wall time,
states and memory depend on the machine and UPPAAL's search order and are reported beside the
paper's values without failing the check.

--smoke and --rerun need the environment variable VERIFYTA (the path of UPPAAL's verifyta binary).
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PY = sys.executable

# ---------------------------------------------------------------- the paper's claims
# query_id: (verdict, witness length in fires or None, states explored)   Section 5.5, first part
BATTERY = {
    "tandem_1__acc": ("SAT", 13, 38), "tandem_2__acc": ("SAT", 15, 98), "tandem_3__acc": ("SAT", 23, 464),
    "tandem_2_batch_shared_p1__ord_P1": ("SAT", 6, 13), "tandem_2_batch_shared_p1__ord_P2": ("UNSAT", None, 41),
    "tandem_2_batch_shared_p2__ord_P1": ("UNSAT", None, 41), "tandem_2_batch_shared_p2__ord_P2": ("SAT", 6, 13),
    "tandem_1_batch__nic": ("SAT", None, 35), "tandem_2_batch__nic": ("SAT", None, 97), "tandem_3_batch__nic": ("SAT", None, 184),
    "tandem_1_batch_norestart__nic": ("UNSAT", 7, 27), "tandem_2_batch_norestart__nic": ("UNSAT", 11, 58),
    "tandem_3_batch_norestart__nic": ("UNSAT", 15, 71),
    "tandem_1_batch__stall": ("UNSAT", None, 27), "tandem_2_batch__stall": ("UNSAT", None, 83), "tandem_3_batch__stall": ("UNSAT", None, 168),
    "tandem_1_batch_norestart__stall": ("SAT", 7, 19), "tandem_2_batch_norestart__stall": ("SAT", 11, 61),
    "tandem_3_batch_norestart__stall": ("SAT", 15, 140),
}
WALL_BOUND_S = 0.07   # "every query completes in at most 0.07 s", compared after rounding to two decimals as the paper prints
# query_id: (verdict, states stored, wall time in s, resident MB)            Section 5.5, second part
EXPLORATION = {
    "tandem_1__zone": ("SAT", 51, 0.05, 20), "tandem_2__zone": ("SAT", 989, 0.07, 20),
    "tandem_3__zone": ("SAT", 22316, 0.56, 32), "tandem_4__frontier": ("SAT", 598737, 33, 234),
    "tandem_5__frontier": ("TIMEOUT", None, 600, None),
}
PROBLEM_OF = {"acc": "ACCESSIBILITY", "ord": "ORDERING", "nic": "NONINTERCHANGEABILITY", "stall": "STALLING"}


# ---------------------------------------------------------------- helpers

def load_merged() -> dict:
    """tables.py merges the result files in precedence order and writes results_merged.csv."""
    import tables
    return tables.load_rows()


def num(x, cast=float):
    try:
        return cast(x)
    except (TypeError, ValueError):
        return None


def check(rows: dict, strict_metrics: bool) -> bool:
    """Compare every claim with the rows. Returns True if every strict comparison passed."""
    ok = True
    print("\nclaims of Section 5.5, first part (verdict, witness length, states explored)")
    for qid, (verdict, fires, states) in BATTERY.items():
        r = rows.get(qid)
        if r is None:
            print(f"  FAIL {qid}: no result row"); ok = False; continue
        got_fires = num(r["witness_len"], int); got_states = num(r["states_explored"], int)
        wall = num(r["wall_s"])
        good = r["verdict"] == verdict and got_fires == fires
        note = ""
        if strict_metrics:
            good = good and got_states == states and wall is not None and round(wall, 2) <= WALL_BOUND_S
        else:
            note = f"   (paper: {states} states; here {got_states} states, {wall:.2f} s)" if wall is not None else ""
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {qid}: {r['verdict']}"
              + (f", {got_fires} fires" if got_fires is not None else "") + f", {r['wall_s']} s, {got_states} states"
              + (f"   expected {verdict}, {fires} fires, {states} states" if not good else note))
    print("\nTable 1, expected verdicts (expected.json) against the results")
    import json
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    for qid in BATTERY:
        e = expected.get(qid); r = rows.get(qid)
        good = r is not None and e == r["verdict"]
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {qid}: expected {e}, got {r['verdict'] if r else 'none'}")
    print("\nclaims of Section 5.5, second part (exhaustive exploration of model (a))")
    for qid, (verdict, stored, wall, mb) in EXPLORATION.items():
        r = rows.get(qid)
        if r is None:
            print(f"  FAIL {qid}: no result row"); ok = False; continue
        got_stored = num(r["states_stored"], int); got_wall = num(r["wall_s"]); got_mb = num(r["resident_mb"])
        good = r["verdict"] == verdict
        if strict_metrics and verdict != "TIMEOUT":
            good = good and got_stored == stored and got_wall is not None and round(got_wall, 2) == wall if wall < 10 else good and got_stored == stored and got_wall is not None and round(got_wall) == wall
            good = good and got_mb is not None and round(got_mb) == mb
        ok = ok and good
        shown = f"{r['verdict']}" + (f", {got_stored} states, {r['wall_s']} s, {r['resident_mb']} MB" if verdict != "TIMEOUT" else f" at {r['timeout_s']} s")
        paper = f"{verdict}" + (f", {stored} states, {wall} s, {mb} MB" if verdict != "TIMEOUT" else f" at {wall} s")
        print(f"  {'PASS' if good else 'FAIL'} {qid}: {shown}" + ("" if good and strict_metrics else f"   (paper: {paper})"))
    print(f"\n{'ALL CLAIMS PASS' if ok else 'SOME CLAIMS FAIL'}"
          + ("" if strict_metrics else " (verdicts and witness lengths; times, states and memory are informative on a rerun)"))
    return ok


def print_results(rows: dict):
    """The Section 5.5 numbers, one line per problem and model, in the paper's order."""
    print("\nSection 5.5, results by problem (verdict, fires, wall time, states explored) at n = 1, 2, 3")
    groups = [("ACCESSIBILITY (a)", ["tandem_{n}__acc"]),
              ("ORDERING (d) under >1: P1, P2", ["tandem_2_batch_shared_p1__ord_P1", "tandem_2_batch_shared_p1__ord_P2"]),
              ("ORDERING (d) under >2: P1, P2", ["tandem_2_batch_shared_p2__ord_P1", "tandem_2_batch_shared_p2__ord_P2"]),
              ("NONINTERCHANGEABILITY (b)", ["tandem_{n}_batch__nic"]), ("NONINTERCHANGEABILITY (c)", ["tandem_{n}_batch_norestart__nic"]),
              ("STALLING (b)", ["tandem_{n}_batch__stall"]), ("STALLING (c)", ["tandem_{n}_batch_norestart__stall"])]
    import tables
    for label, pats in groups:
        cells = []
        for pat in pats:
            if "{n}" in pat:
                cells += [tables.result_cell(rows.get(pat.format(n=n))) for n in (1, 2, 3)]
            else:
                cells.append(tables.result_cell(rows.get(pat)))
        print(f"  {label}: " + " | ".join(cells))
    print("\nSection 5.5, exhaustive exploration of model (a), n = 1..5 (states stored, wall time, resident MB)")
    for n in (1, 2, 3, 4, 5):
        r = rows.get(f"tandem_{n}__zone") or rows.get(f"tandem_{n}__frontier")
        if r is None:
            print(f"  n = {n}: no row"); continue
        if r["verdict"] == "TIMEOUT":
            print(f"  n = {n}: timeout at {float(r['timeout_s']):.0f} s")
        else:
            print(f"  n = {n}: {r['states_stored']} states, {tables.fmt_wall(float(r['wall_s']))}, {float(r['resident_mb']):.0f} MB")


def run(args, **kw):
    print("$ " + " ".join(str(a) for a in args))
    return subprocess.run([str(a) for a in args], cwd=HERE, **kw)


@contextlib.contextmanager
def keep_run_of_record():
    """run.py rewrites results/host.json and results/traces/ on every run; a rerun must not
    overwrite the run of record, so both are restored afterwards."""
    with tempfile.TemporaryDirectory() as tmp:
        host = RES / "host.json"; traces = RES / "traces"
        if host.exists():
            shutil.copy2(host, Path(tmp) / "host.json")
        if traces.exists():
            shutil.copytree(traces, Path(tmp) / "traces")
        try:
            yield
        finally:
            if (Path(tmp) / "host.json").exists():
                shutil.copy2(Path(tmp) / "host.json", host)
            if (Path(tmp) / "traces").exists():
                shutil.rmtree(traces, ignore_errors=True); shutil.copytree(Path(tmp) / "traces", traces)


def need_verifyta():
    v = os.environ.get("VERIFYTA")
    if not v or not Path(v).exists():
        raise SystemExit("reproduce.py: set VERIFYTA to the path of UPPAAL's verifyta binary (see README, Requirements)")
    return v


# ---------------------------------------------------------------- modes

def smoke():
    need_verifyta()
    out = RES / "smoke.csv"
    with keep_run_of_record():
        run([PY, "run.py", "--xml", "models/uppaal/tandem_1.xml", "--q", "queries/tandem_1__acc.q", "--out", out], check=True)
    with out.open(encoding="utf-8") as fh:
        r = next(csv.DictReader(fh))
    good = r["verdict"] == "SAT" and num(r["witness_len"], int) == 13
    print(f"\n{'PASS' if good else 'FAIL'}: tandem_1, ACCESSIBILITY: {r['verdict']}, {r['witness_len']} fires, {r['wall_s']} s "
          f"(paper: SAT, 13 fires)")
    out.unlink(missing_ok=True)
    return good


def rerun(skip_timeout: bool):
    need_verifyta()
    tmp = [RES / "rerun_battery.csv", RES / "rerun_frontier4.csv", RES / "rerun_frontier5.csv"]
    with keep_run_of_record():
        run([PY, "run.py", "--only", "tandem", "--exclude", "frontier", "--out", tmp[0]], check=True)
        run([PY, "run.py", "--only", "tandem_4", "--out", tmp[1]], check=True)
        if not skip_timeout:
            run([PY, "run.py", "--only", "tandem_5", "--out", tmp[2]], check=True)
    # results/results.csv overrides every recorded file in tables.py's precedence
    rows = []
    for f in tmp:
        if f.exists():
            with f.open(encoding="utf-8") as fh:
                rows += list(csv.DictReader(fh))
            f.unlink()
    target = RES / "results.csv"
    with target.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"\n{target.name}: {len(rows)} fresh rows (they override the recorded runs in tables.py; delete the file to return to the run of record)")
    merged = load_merged()
    if skip_timeout:
        EXPLORATION.pop("tandem_5__frontier", None)
    print_results(merged)
    return check(merged, strict_metrics=False)


def recorded():
    import tables
    rows = load_merged()
    tables.table1_design(tables.load_expected()); tables.results_by_problem(rows); tables.exploration(rows)
    print_results(rows)
    return check(rows, strict_metrics=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true", help="installation check: one query with UPPAAL")
    ap.add_argument("--rerun", action="store_true", help="rerun every query of the paper with UPPAAL, then check")
    ap.add_argument("--skip-timeout", action="store_true", help="with --rerun, leave out the 600 s row at n = 5")
    a = ap.parse_args()
    if a.smoke:
        ok = smoke()
    elif a.rerun:
        ok = rerun(a.skip_timeout)
    else:
        ok = recorded()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
