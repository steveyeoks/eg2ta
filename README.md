# eg2ta: Event Graph to UPPAAL, the experiments of the paper's §5

This folder is the implementation and the experiments behind §5 of *Model Checking
Event Graph Simulation Models through Timed Automata*. It holds a generator for the
benchmark Event Graphs (EG), the translation τ from an EG to a UPPAAL network of timed
automata (Definitions 3.1 to 3.5 of the paper), the queries that pose the four
Jacobson-Yücesan search problems (ACCESSIBILITY, ORDERING, NONINTERCHANGEABILITY,
STALLING) on those models, a runner for UPPAAL's `verifyta`, and the scripts that turn
the recorded results into the paper's tables. Everything is plain Python with no
third-party packages, and nothing is imported from outside this folder.

## Requirements

- Python 3.9 or later, standard library only.
- UPPAAL 5.0.0, for its command-line checker `verifyta`. Set the environment variable
  `VERIFYTA` to the path of the binary before running `run.py`; the script refuses to
  start without it. On macOS:

      export VERIFYTA=/Applications/UPPAAL-5.0.0.app/Contents/Resources/uppaal/bin/verifyta

  The UPPAAL 5.0.0 distribution for macOS is an x86-64 build and runs under Rosetta on
  Apple silicon. Before the first run, remove the quarantine flag from the downloaded
  application (`xattr -dr com.apple.quarantine /Applications/UPPAAL-5.0.0.app`) and
  activate the license once, as described on the UPPAAL download page; after that
  `verifyta --version` prints `UPPAAL 5.0.0 (rev. 714BA9DB36F49691), June 2023`.

## Regenerating everything, in order

    python3 gen_models.py           # models/eg/*.json, the benchmark Event Graphs
    python3 eg2xml.py --all         # models/uppaal/*.xml, the translation tau of each EG
    python3 queries.py              # queries/*.q and expected.json
    python3 run.py                  # verifyta on every query: results/results.csv, traces/, logs/, host.json
    python3 tables.py               # tables/*.md and *.tex, the paper's tables
    python3 count_elements.py       # EG and NTA sizes for every model, CSV on stdout

`gen_models.py`, `queries.py` and `count_elements.py` take no arguments, `eg2xml.py`
takes `--all` (or one source file), and none of the four needs UPPAAL. `run.py` accepts
`--only PREFIX` (query ids to run), `--exclude SUBSTRING` (query ids to skip),
`--timeout SECONDS` (per query, default 600), `--out FILE` (default
`results/results.csv`), `--no-trace`, and `--xml MODEL --q QUERY --out FILE` for one
explicit pair (a smoke test: the three must be given together, and only that file is
written, not `host.json`).
`tables.py` reads, in increasing precedence, `results/results_extra.csv`,
`results/results_battery.csv`, `results/results_frontier.csv` and, if it exists,
`results/results.csv` (the output of a full `run.py`, which overrides all); a later file
overrides an earlier one per query id, and the script prints which files it read and in
what order. It writes the merge to `results/results_merged.csv` and then the four paper
tables; `tables.py --all` also writes the three full tables over every model. The
committed `results/` already holds the run of record, so `tables.py` works on a fresh
clone without any run.

### Quick start: the paper's tables in about 12 minutes

    export VERIFYTA=/Applications/UPPAAL-5.0.0.app/Contents/Resources/uppaal/bin/verifyta
    python3 run.py --only tandem --exclude frontier --out results/results_battery.csv   # 5 s
    python3 run.py --only tandem_4 --out results/results_frontier.csv                   # 35 s
    python3 run.py --only tandem_5 --out results/results_frontier_b.csv                 # 600 s, the timeout row
    tail -n +2 results/results_frontier_b.csv >> results/results_frontier.csv
    python3 tables.py

The second command overwrites the committed `results_frontier.csv`, which held both
frontier rows, with the `tandem_4` row alone; the third is the 600 s timeout row
(`tandem_5`), written to its own file so that it does not overwrite `tandem_4`, and the
`tail` appends it. `tables.py` reads only the files named above (any other
`results_*.csv` is reported and ignored), and a later file overrides an earlier one per
query id, so a leftover `results/results.csv` from a full run would take precedence over
all of these. Skip the `tandem_5` step and the `tail` to finish in under a minute with
the `n = 5` column blank.

## What each folder holds

- `models/eg/`: 37 Event Graphs as JSON, written by `gen_models.py`. Names are
  `<topology>_<n>[_variant]`: the tandem, fork-join and feedback networks at
  `n = 1..5` stations, plus the terminating `_batch` variants, their faulty
  implementations (`_norestart`, `_nojoin`, `_nodepartcheck`), the shared-server
  tandem `_batch_shared_p1`/`_p2`/`_p3`/`_p3_wide` (three tie-breaking orders and a
  widened domain), the `_alt` and `_permuted` order variants, and the multi-server
  `_c2`/`_c5` checks.
- `models/uppaal/`: the 37 UPPAAL XML files, one per EG, written by `eg2xml.py`.
- `queries/`: 110 query files, one formula each, named `<model>__<label>.q` and run
  against `models/uppaal/<model>.xml`. Labels: `acc` and `acc_*` (ACCESSIBILITY), `ord_P1`/`ord_P2`
  and `ord_over` (ORDERING), `nic` (NONINTERCHANGEABILITY), `stall` and `term`
  (STALLING and its complement), `cost` (a leads-to that forces exhaustive search),
  `zone` and `frontier` (`A[] true`, the whole reachable state space).
- `expected.json`: 104 verdicts, one per query except the frontier probes, written
  before any run; `run.py` prints `<-- DIFF` on a mismatch and `tables.py` takes the
  expected verdicts of Table 5.2 from here.
- `results/`: the recorded runs. `results_battery.csv` is the run of record for the
  tandem models (56 rows), `results_frontier.csv` the exhaustive runs at `n = 4` and
  `n = 5`, `results_extra.csv` the fork-join and feedback rows (52 rows),
  `results_merged.csv` the merge written by `tables.py` (`results.csv`, the output of a
  full `run.py`, is not committed), `host.json` the verifyta version and
  machine of the last run, and `traces/` the verifyta output of every query that produced
  a trace. `logs/` (raw verifyta output per query) and the console `*.log` files are
  not tracked.
- `tables/`: `table52_design`, `table53_results`, `table54_exploration` and
  `tableA1_models`, each as Markdown and as a LaTeX `tabular`, regenerated by
  `tables.py`. With `--all`, also `table51_models`, `table52_results` and
  `table53_frontier` over every model.
- `smoke/`: the first end-to-end evidence: `mm1_golden.xml`, a read-only reference
  M/M/1 model from an earlier tool, with `mm1_golden__bounds.q` and
  `mm1_golden__reach.q`, `true.q`, and the ORDERING predicates `shared_P1.q`,
  `shared_P2.q`, `shared_over.q`.
- `count_elements.py`: the EG and NTA size counts (vertices, timed and zero-delay
  edges, variables, valuations; automata, locations, branchpoints, transitions, clocks,
  channels, shared variables) that `tables.py` imports.

## The run of record

The results in `results/` were produced on a Mac with Apple silicon (`results/host.json`)
running the x86-64 build of verifyta 5.0.0 under Rosetta, single runs with a budget of
600 s per query: `run.py --only tandem --exclude frontier` for the battery and the two
frontier queries `tandem_4__frontier` and `tandem_5__frontier` separately.

The paper reports the tandem models: the nonterminating tandem `n` queue, its
terminating variant, the faulty implementation of that variant, and the shared-server
tandem, at `n = 1, 2, 3` for the four problems and `n = 1..5` for exhaustive
exploration. The fork-join and feedback networks are extra material with the same
battery of queries; their rows live in `results/results_extra.csv` and appear only in
the `--all` tables.

## Verdicts

Every row of a results CSV has one of five verdicts:

- `SAT`: verifyta reports the formula satisfied.
- `UNSAT`: verifyta reports it not satisfied.
- `RANGE`: verifyta stopped on an assignment outside a variable's declared range, so
  the EG leaves its declared variable domain along some run (the `[var := value]` note
  is appended to the query column; `tandem_2_batch_shared_p3` is RANGE by design).
- `TIMEOUT`: the per-query budget (`timeout_s`) was exhausted.
- `ERROR`: no verdict could be parsed from the output; the reason is appended to the
  query column and the full output is in `results/logs/`.

Whenever verifyta prints a trace, a witness for a satisfied `E<>` or a counterexample
for a failed leads-to or `A[]`, `run.py` saves it under `results/traces/` and fills
`witness_len` with its number of fire actions.
