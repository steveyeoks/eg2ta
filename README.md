# eg2ta: model checking bounded Event Graphs through timed automata

The implementation and the experiments of Section 5 of *On Model Checking of Bounded Event
Graph Discrete-Event Simulation Models via Timed Automata* (submitted to ACM SIGSIM-PADS
2027). It holds a generator for the benchmark Event Graphs (EG), the translation τ from an EG
to a UPPAAL network of timed automata, the queries that pose the four search problems of
Jacobson and Yücesan (ACCESSIBILITY, ORDERING, NONINTERCHANGEABILITY, STALLING) on those
models, a runner for UPPAAL's `verifyta`, the recorded runs the paper reports, and one script
that regenerates and checks every number in the paper. Everything is plain Python with no
third-party packages.

**In one command, without UPPAAL:** `python3 reproduce.py` regenerates the paper's Table 1
and the numbers of Section 5.5 from the recorded runs and prints PASS or FAIL for every claim,
in about two seconds. **With UPPAAL:** `python3 reproduce.py --rerun` reruns every query
(about 12 minutes, 10 of them the timeout row) and checks the fresh results.

## Requirements

- **Python 3.9 or later**, standard library only. Tested with 3.9.6.
- **UPPAAL 5.0.0**, only for rerunning the queries; the recorded runs need no UPPAAL. Download
  it from https://uppaal.org/downloads/ (free academic license, activated once per machine as
  the download page describes; the license does not allow the binary to be redistributed, so
  it is not part of this repository). Set `VERIFYTA` to the path of the command-line checker:

      # macOS
      export VERIFYTA=/Applications/UPPAAL-5.0.0.app/Contents/Resources/uppaal/bin/verifyta
      # Linux (unpacked zip)
      export VERIFYTA=$HOME/uppaal-5.0.0-linux64/bin/verifyta
      # Windows (PowerShell)
      $env:VERIFYTA = "C:\uppaal-5.0.0-win64\bin\verifyta.exe"

  The macOS build is x86-64 and runs under Rosetta on Apple silicon; before the first run,
  remove the quarantine flag (`xattr -dr com.apple.quarantine /Applications/UPPAAL-5.0.0.app`).
  `verifyta --version` should print `UPPAAL 5.0.0 (rev. 714BA9DB36F49691), June 2023`.
- **Hardware:** any laptop. The largest run (`tandem_4`, exhaustive exploration) peaks at
  234 MB of resident memory; the repository is under 5 MB. The run of record used an Apple M2.

## Installation check

    export VERIFYTA=...          # as above
    python3 reproduce.py --smoke

runs one query (ACCESSIBILITY on the tandem-1 queue) and prints `PASS: ... SAT, 13 fires`.
About one second, a few seconds on the first launch of verifyta.

## Reproducing the paper

Step 1 needs no UPPAAL and is what the paper's tables and prose were pasted from.

    python3 reproduce.py                  # about 2 s: merge the recorded runs, write tables/,
                                          # print the Section 5.5 numbers, check every claim
    python3 reproduce.py --rerun          # about 12 min with UPPAAL: rerun every query, then check
    python3 reproduce.py --rerun --skip-timeout   # under 1 min: the same without the 600 s row

What the checks cover, and what they treat as reproducible:

| paper | claim | script | strict on recorded runs | strict on a rerun |
|---|---|---|---|---|
| Table 1 | the expected verdict of every row, from `expected.json` | `tables.py` (`tables/table1_design`) | yes | yes |
| Section 5.5, results by problem | verdict, witness length in fires, states explored, every query in at most 0.07 s | `tables.py` (`tables/results_by_problem`) | yes | verdict and witness length; states and time are reported beside the paper's values |
| Section 5.5, exhaustive exploration | verdict, states stored, wall time, resident memory at n = 1..5 | `tables.py` (`tables/exploration`) | yes | verdict; the rest reported |

Wall times, memory and state counts depend on the machine and on UPPAAL's search order, which
is why a rerun checks them only as informative. Verdicts and witness lengths are what the paper's
argument rests on, and a rerun must reproduce them exactly. A rerun writes `results/results.csv`,
which takes precedence over the recorded files; delete it to return to the run of record.

The figures of the paper are drawings of the models and the construction, not results, and
have no script. `python3 tables.py --all` also writes the size table of the benchmark models and
three full tables over every model and query, extra material beyond the paper.

## Regenerating everything from the Event Graphs

`reproduce.py` starts from the recorded runs. The pipeline that produced them, in order:

    python3 gen_models.py           # models/eg/*.json, the benchmark Event Graphs
    python3 eg2xml.py --all         # models/uppaal/*.xml, the translation tau of each EG
    python3 queries.py              # queries/*.q and expected.json
    python3 run.py                  # verifyta on every query: results/results.csv, traces/, host.json
    python3 tables.py               # tables/*.md and *.tex

`run.py` accepts `--only PREFIX`, `--exclude SUBSTRING`, `--timeout SECONDS` (default 600),
`--out FILE`, `--no-trace`, and `--xml MODEL --q QUERY --out FILE` for one explicit pair.
`tables.py` reads, in increasing precedence, `results/results_extra.csv`,
`results/results_battery.csv`, `results/results_frontier.csv` and, if present,
`results/results.csv`, merges them into `results/results_merged.csv`, and writes the tables.

## What each folder holds

- `models/eg/`: 37 Event Graphs as JSON, written by `gen_models.py`. Names are
  `<topology>_<n>[_variant]`: the tandem, fork-join and feedback networks at `n = 1..5`
  stations, the terminating `_batch` variants, their faulty implementations (`_norestart`,
  `_nojoin`, `_nodepartcheck`), the shared-server tandem `_batch_shared_p1`/`_p2`/`_p3`/
  `_p3_wide` (three tie-breaking orders and a widened domain), the `_alt` and `_permuted`
  order variants, and the multi-server `_c2`/`_c5` checks.
- `models/uppaal/`: the 37 UPPAAL XML files, one per EG, written by `eg2xml.py`.
- `queries/`: 110 query files, one formula each, named `<model>__<label>.q` and run against
  `models/uppaal/<model>.xml`. Labels: `acc` and `acc_*` (ACCESSIBILITY), `ord_P1`/`ord_P2`
  and `ord_over` (ORDERING), `nic` (NONINTERCHANGEABILITY), `stall` and `term` (STALLING and
  its complement), `cost` (a leads-to that forces exhaustive search), `zone` and `frontier`
  (`A[] true`, the whole reachable state space).
- `expected.json`: 104 verdicts, one per query except the frontier probes, written before any
  run; `run.py` prints `<-- DIFF` on a mismatch and Table 1 is generated from it.
- `results/`: the recorded runs. `results_battery.csv` is the run of record for the tandem
  models (56 rows), `results_frontier.csv` the exhaustive runs at `n = 4` and `n = 5`,
  `results_extra.csv` the fork-join and feedback rows (52 rows), `results_merged.csv` the
  merge written by `tables.py`, `host.json` the verifyta version and machine of the run of
  record, and `traces/` the verifyta output of every query that produced a trace. `logs/`
  (raw verifyta output per query) and the console `*.log` files are not tracked.
- `tables/`: `table1_design`, `results_by_problem` and `exploration`, each as Markdown and as
  a LaTeX `tabular`, regenerated by `tables.py`; with `--all`, also `tableA1_models`,
  `table51_models`, `table52_results` and `table53_frontier`.
- `smoke/`: the first end-to-end evidence: `mm1_golden.xml`, a read-only reference M/M/1 model
  from an earlier tool, with its queries.
- `count_elements.py`: the EG and NTA size counts that `tables.py` imports.
- `reproduce.py`: the one-command entry point described above.

## The run of record

The results in `results/` were produced on an Apple M2 laptop (`results/host.json`: macOS,
arm64, Python 3.9.6) running the x86-64 build of verifyta 5.0.0 under Rosetta, single runs with
a budget of 600 s per query: `run.py --only tandem --exclude frontier` for the battery and the
two frontier queries `tandem_4__frontier` and `tandem_5__frontier` separately. The same battery
run earlier on a Windows laptop gave the same verdicts, witness lengths and state counts.

The paper reports the tandem models: the nonterminating tandem `n` queue, its terminating
variant, the faulty implementation of that variant, and the shared-server tandem, at
`n = 1, 2, 3` for the four problems and `n = 1..5` for exhaustive exploration. The fork-join
and feedback networks are extra material with the same battery of queries; their rows live in
`results/results_extra.csv` and appear only in the `--all` tables.

## Verdicts

Every row of a results CSV has one of five verdicts:

- `SAT`: verifyta reports the formula satisfied.
- `UNSAT`: verifyta reports it not satisfied.
- `RANGE`: verifyta stopped on an assignment outside a variable's declared range, so the EG
  leaves its declared variable domain along some run (the `[var := value]` note is appended to
  the query column; `tandem_2_batch_shared_p3` is RANGE by design).
- `TIMEOUT`: the per-query budget (`timeout_s`) was exhausted.
- `ERROR`: no verdict could be parsed from the output; the reason is appended to the query
  column and the full output is in `results/logs/`.

Whenever verifyta prints a trace, a witness for a satisfied `E<>` or a counterexample for a
failed leads-to or `A[]`, `run.py` saves it under `results/traces/` and fills `witness_len`
with its number of fire actions.

## License and citation

MIT, see `LICENSE`. To cite, use `CITATION.cff` (GitHub shows it under "Cite this repository").
