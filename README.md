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

- **Hardware:** a laptop with 1 GB of free memory is recommended. The largest run
  (`tandem_4`, exhaustive exploration) peaks at 234 MB of resident memory, and the repository
  is under 5 MB. The run of record used an Apple M2.

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

A rerun writes `results/results.csv`, which takes precedence over the recorded runs; delete it
to return to the run of record.

## Regenerating everything from the Event Graphs

`reproduce.py` starts from the recorded runs. The pipeline that produced them, in order:

    python3 gen_models.py           # models/eg/*.json, the benchmark Event Graphs
    python3 eg2xml.py --all         # models/uppaal/*.xml, the translation tau of each EG
    python3 queries.py              # queries/*.q and expected.json
    python3 run.py                  # verifyta on every query: results/results.csv, traces/, host.json
    python3 tables.py               # tables/*.md and *.tex

`reproduce.py`, `eg2xml.py`, `run.py` and `tables.py` print their options with `--help`.

## Repository layout

    eg2ta/
    ├── reproduce.py            one-command entry point
    ├── gen_models.py           writes the benchmark Event Graphs
    ├── eg2xml.py               the translation tau, EG JSON to UPPAAL XML
    ├── queries.py              writes the queries and expected.json
    ├── run.py                  runs verifyta on every query
    ├── tables.py               merges the recorded runs and writes the tables
    ├── count_elements.py       EG and NTA size counts used by tables.py
    ├── expected.json           the expected verdict of every query, fixed before any run
    ├── models/
    │   ├── eg/                 37 Event Graphs as JSON, <topology>_<n>[_variant].json
    │   └── uppaal/             their UPPAAL translations, one XML file per EG
    ├── queries/                110 query files, <model>__<label>.q
    ├── results/
    │   ├── results_battery.csv     run of record, tandem models
    │   ├── results_frontier.csv    exhaustive exploration at n = 4 and 5
    │   ├── results_extra.csv       fork-join and feedback networks
    │   ├── results_merged.csv      the merge written by tables.py
    │   ├── host.json               verifyta version and machine of the run of record
    │   ├── traces/                 verifyta traces of every query that produced one
    │   └── logs/                   raw verifyta output, not tracked
    ├── tables/                 the paper's tables as Markdown and LaTeX
    └── smoke/                  a reference M/M/1 model and its queries

Model names are `<topology>_<n>[_variant]`, the tandem, fork-join and feedback networks at
`n = 1..5` stations, with `_batch` for the terminating variants, `_norestart`, `_nojoin`,
`_nodepartcheck` for their faulty implementations, and `_batch_shared_p1`, `_batch_shared_p2`
for the shared-server tandem under the two tie-breaking orders. Query labels are `acc` (ACCESSIBILITY),
`ord_P1` and `ord_P2` (ORDERING), `nic` (NONINTERCHANGEABILITY), `stall` (STALLING), and
`zone` and `frontier` (`A[] true`, exhaustive exploration).

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

## License

MIT, see `LICENSE`.
