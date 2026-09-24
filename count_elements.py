"""count_elements.py: EG and NTA size counts for Table 5.1.

    python count_elements.py                 # every models/eg/*.json with its XML, CSV to stdout
    python count_elements.py path.xml ...    # XML-only counts

EG: vertices (excluding Run), timed edges, zero-delay edges (seed edges included),
state variables, product of (bound+1). NTA: automata, locations, branchpoints,
transitions, clocks, channels, shared variables.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
EG_DIR = HERE / "models" / "eg"
XML_DIR = HERE / "models" / "uppaal"

EG_COLS = ["vertices", "timed_edges", "zero_edges", "variables", "valuations"]
NTA_COLS = ["automata", "locations", "branchpoints", "transitions", "clocks", "channels", "shared_vars"]


def count_eg(path: Path) -> dict:
    eg = json.loads(path.read_text(encoding="utf-8"))
    prod = 1
    for v in eg["variables"].values():
        prod *= v["bound"] + 1
    return dict(
        vertices=len(eg["vertices"]) - 1,
        timed_edges=sum(1 for e in eg["edges"] if e["delay"] != [0, 0]),
        zero_edges=sum(1 for e in eg["edges"] if e["delay"] == [0, 0]),
        variables=len(eg["variables"]),
        valuations=prod,
    )


def count_xml(path: Path) -> dict:
    root = ET.parse(path).getroot()
    decl = root.findtext("declaration") or ""
    chans = 0
    for line in decl.splitlines():
        line = line.strip()
        if line.startswith(("chan ", "broadcast chan ")) and not line.startswith("chan priority"):
            chans += line.rstrip(";").split(" chan ")[-1].replace("chan ", "").count(",") + 1
    shared = len(re.findall(r"^int\[", decl, re.M))
    templates = root.findall("template")
    return dict(
        automata=len(templates),
        locations=sum(len(t.findall("location")) for t in templates),
        branchpoints=sum(len(t.findall("branchpoint")) for t in templates),
        transitions=sum(len(t.findall("transition")) for t in templates),
        clocks=sum((t.findtext("declaration") or "").count("clock") for t in templates),
        channels=chans,
        shared_vars=shared,
    )


def main(argv):
    if argv:
        print("model," + ",".join(NTA_COLS))
        for p in argv:
            c = count_xml(Path(p))
            print(Path(p).stem + "," + ",".join(str(c[k]) for k in NTA_COLS))
        return
    print("model," + ",".join(EG_COLS + NTA_COLS))
    for src in sorted(EG_DIR.glob("*.json")):
        row = count_eg(src)
        xml = XML_DIR / (src.stem + ".xml")
        row.update(count_xml(xml) if xml.exists() else {k: "" for k in NTA_COLS})
        print(src.stem + "," + ",".join(str(row[k]) for k in EG_COLS + NTA_COLS))


if __name__ == "__main__":
    main(sys.argv[1:])
