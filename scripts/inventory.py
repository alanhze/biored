# scripts/inventory.py
"""Count documents, mentions and relations in every BioC XML and PubTator file under data/raw."""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
DOC_HEADER = re.compile(r"^\S+\|[ta]\|")


def count_xml(p):
    docs = mentions = relations = 0
    for _, el in ET.iterparse(p, events=("end",)):
        if el.tag == "document":
            docs += 1
            el.clear()  # keep memory flat on the 10,000-document test file
        elif el.tag == "annotation":
            mentions += 1
        elif el.tag == "relation":
            relations += 1
    return docs, mentions, relations, 0, 0


def count_pubtator(p):
    docs = set()
    mentions = relations = directions = other = 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        if DOC_HEADER.match(line):
            if "|t|" in line:
                docs.add(line.split("|t|", 1)[0])
            continue
        f = line.split("\t")
        if len(f) >= 6 and f[1].isdigit() and f[2].isdigit():
            mentions += 1                      # PMID start end text type id(s)
        elif len(f) == 4 and f[3].startswith("Subject:"):
            directions += 1                    # BioREDirect: PMID id1 id2 Subject:<id>
        elif len(f) >= 5 and not f[1].isdigit():
            relations += 1                     # BioRED: PMID type id1 id2 novelty
        elif len(f) == 4 and not f[1].isdigit():
            relations += 1                     # CDR: PMID CID chem disease
        else:
            other += 1                         # malformed or unexpected lines
    return len(docs), mentions, relations, directions, other


for p in sorted(ROOT.rglob("*")):
    if not p.is_file():
        continue
    suffix = p.suffix.lower()
    if suffix == ".xml":
        counts = count_xml(p)
    elif suffix in {".pubtator", ".txt"}:
        counts = count_pubtator(p)
        if counts[0] == 0:
            continue  # README or other non-PubTator text file
    else:
        continue
    docs, mentions, relations, directions, other = counts
    note = (f" directions={directions}" if directions else "") + (f" other={other}" if other else "")
    print(f"{p}: docs={docs} mentions={mentions} relations={relations}{note}")