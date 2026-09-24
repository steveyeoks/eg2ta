"""run.py: run verifyta on (model.xml, query.q) pairs and record one CSV row per query.

Usage:
    python run.py                       # every queries/*.q against its model
    python run.py --only tandem_2       # queries whose name starts with tandem_2
    python run.py --xml X --q Q         # one explicit pair (smoke test)
    python run.py --timeout 600         # per-query timeout in seconds

Pairing rule: queries/<model>__<label>.q runs against models/uppaal/<model>.xml.

Each row: query_id, model, xml_sha, query, expected, verdict, wall_s, cpu_s,
resident_mb, virtual_mb, states_stored, states_explored, witness_len, timeout_s, timestamp.
Timeouts are rows with verdict TIMEOUT. Unparseable output is an error row, never a silent blank.
Whenever verifyta prints a trace (a witness for a satisfied E<>, a counterexample for a
failed leads-to or A[]), it is saved to results/traces/<query_id>.trace.txt and witness_len
is its number of fire actions.

The environment variable VERIFYTA must hold the path of UPPAAL's verifyta binary.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE / "models" / "uppaal"
QUERIES = HERE / "queries"
RESULTS = HERE / "results"
TRACES = RESULTS / "traces"
LOGS = RESULTS / "logs"

COLUMNS = ["query_id", "model", "xml_sha", "query", "expected", "verdict",
           "wall_s", "cpu_s", "resident_mb", "virtual_mb", "states_stored",
           "states_explored", "witness_len", "timeout_s", "timestamp"]

# verifyta 5.0.0 -u output lines (one block per formula)
RE_VERDICT = re.compile(r"Formula is (satisfied|NOT satisfied)")
RE_STORED = re.compile(r"States stored\s*:\s*(\d+)")
RE_EXPLORED = re.compile(r"States explored\s*:\s*(\d+)")
RE_CPU = re.compile(r"CPU user time used\s*:\s*([\d.]+)\s*ms")
RE_VIRT = re.compile(r"Virtual memory used\s*:\s*(\d+)\s*KiB")
RE_RES = re.compile(r"Resident memory used\s*:\s*(\d+)\s*KiB")
RE_ERROR = re.compile(r"^\[error\]|syntax error|Cannot handle", re.M)
RE_RANGE = re.compile(r"Assignment of value '(-?\d+)' to variable '(\w+)' is out of range")
RE_TRACE = re.compile(r"^(Transition|State):", re.M)


def verifyta() -> Path:
    """The verifyta binary named by the environment variable VERIFYTA (required)."""
    v = os.environ.get("VERIFYTA")
    if not v:
        raise SystemExit("run.py: the environment variable VERIFYTA is not set; point it at UPPAAL's "
                         "verifyta binary, e.g.\n"
                         "  export VERIFYTA=/Applications/UPPAAL-5.0.0.app/Contents/Resources/uppaal/bin/verifyta")
    p = Path(v)
    if not p.is_file():
        raise SystemExit(f"run.py: VERIFYTA={v} is not a file")
    return p


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def read_query(qpath: Path) -> str:
    """The single formula in a .q file (comments stripped)."""
    lines = [l for l in qpath.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("//")]
    if len(lines) != 1:
        raise SystemExit(f"{qpath}: expected exactly one formula line, got {len(lines)}")
    return lines[0].strip()


def witness_length(text: str) -> str:
    """Number of fire synchronisations in a concrete trace (-t 0 -y), or ''."""
    fires = re.findall(r"fire_\w+[!?]", text)
    return str(len(fires) // 2) if fires else ""


def run_one(xml: Path, qpath: Path, timeout: float, expected: str = "",
            trace: bool = True) -> dict:
    cmd = [str(verifyta()), "-u"]
    if trace:
        cmd += ["-t", "0", "-y"]
    cmd += [str(xml), str(qpath)]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        wall = time.perf_counter() - t0
        out = proc.stdout + "\n" + proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as ex:
        wall = time.perf_counter() - t0
        out = (ex.stdout or b"").decode(errors="replace") if isinstance(ex.stdout, bytes) else (ex.stdout or "")
        timed_out = True
    qid = qpath.stem
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{qid}.log").write_text(out, encoding="utf-8")

    row = dict.fromkeys(COLUMNS, "")
    row.update(query_id=qid, model=xml.stem, xml_sha=sha(xml), query=read_query(qpath),
               expected=expected, wall_s=f"{wall:.3f}", timeout_s=str(timeout),
               timestamp=datetime.now().isoformat(timespec="seconds"))
    if timed_out:
        row["verdict"] = "TIMEOUT"
        return row
    m = RE_VERDICT.search(out)
    rng = RE_RANGE.search(out)
    if rng:
        # verifyta aborts on an out-of-range assignment: a reachable bound violation,
        # reported as its own verdict (the EG leaves its declared variable domain)
        row["verdict"] = "RANGE"
        row["query"] += f"  [{rng.group(2)} := {rng.group(1)}]"
        if trace:
            TRACES.mkdir(parents=True, exist_ok=True)
            (TRACES / f"{qid}.trace.txt").write_text(out, encoding="utf-8")
            row["witness_len"] = witness_length(out)
        return row
    if not m:
        row["verdict"] = "ERROR"
        err = RE_ERROR.search(out)
        row["query"] += "  [" + (err.group(0) if err else "no verdict in output") + "]"
        return row
    row["verdict"] = "SAT" if m.group(1) == "satisfied" else "UNSAT"
    for key, rx, scale in (("states_stored", RE_STORED, 1), ("states_explored", RE_EXPLORED, 1),
                           ("cpu_s", RE_CPU, 1 / 1000), ("virtual_mb", RE_VIRT, 1 / 1024),
                           ("resident_mb", RE_RES, 1 / 1024)):
        mm = rx.search(out)
        if mm:
            v = float(mm.group(1)) * scale
            row[key] = str(int(v)) if scale == 1 else f"{v:.3f}"
    if trace and RE_TRACE.search(out):
        # any trace: a witness for a satisfied E<>, a counterexample for a failed --> or A[]
        TRACES.mkdir(parents=True, exist_ok=True)
        (TRACES / f"{qid}.trace.txt").write_text(out, encoding="utf-8")
        row["witness_len"] = witness_length(out)
    return row


def write_host():
    RESULTS.mkdir(parents=True, exist_ok=True)
    ver = subprocess.run([str(verifyta()), "--version"], capture_output=True, text=True).stdout
    info = {"verifyta": ver.splitlines()[0] if ver else "?", "python": sys.version.split()[0],
            "machine": platform.machine(), "processor": platform.processor(),
            "os": platform.platform(), "date": datetime.now().isoformat(timespec="seconds")}
    (RESULTS / "host.json").write_text(json.dumps(info, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="prefix of query ids to run")
    ap.add_argument("--exclude", default="", help="substring of query ids to skip (e.g. frontier)")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--xml")
    ap.add_argument("--q")
    ap.add_argument("--out", default=str(RESULTS / "results.csv"))
    ap.add_argument("--no-trace", action="store_true")
    a = ap.parse_args()
    verifyta()  # fail early, before any file is touched

    expected = {}
    exp_path = HERE / "expected.json"
    if exp_path.exists():
        expected = json.loads(exp_path.read_text(encoding="utf-8"))

    if a.xml and a.q:
        pairs = [(Path(a.xml), Path(a.q))]
    else:
        pairs = []
        for q in sorted(QUERIES.glob("*.q")):
            if a.only and not q.stem.startswith(a.only):
                continue
            if a.exclude and a.exclude in q.stem:
                continue
            model = q.stem.split("__")[0]
            pairs.append((MODELS / f"{model}.xml", q))
    write_host()
    rows = []
    for xml, q in pairs:
        row = run_one(xml, q, a.timeout, expected.get(q.stem, ""), trace=not a.no_trace)
        rows.append(row)
        flag = "" if not row["expected"] or row["expected"] == row["verdict"] else "  <-- DIFF"
        print(f"{row['query_id']:40s} {row['verdict']:8s} {row['wall_s']:>8s} s  "
              f"{row['states_explored']:>8s} st  {row['resident_mb']:>8s} MB{flag}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
