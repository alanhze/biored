"""Check that the BioC XML and PubTator loaders read the same file identically.

Usage: python scripts/compare_formats.py data/raw/BIORED/BioRED/Train.BioC.XML data/raw/BIORED/BioRED/Train.PubTator
(use the exact names inventory.py printed). Compares text, entities, mentions and relations per PMID.
"""
import sys

from biored.data import load_any

xml_docs = {d.pmid: d for d in load_any(sys.argv[1])}
pt_docs = {d.pmid: d for d in load_any(sys.argv[2])}
problems = []
if xml_docs.keys() != pt_docs.keys():
    problems.append(f"PMID sets differ: {len(xml_docs.keys() ^ pt_docs.keys())} not shared")
for pmid in sorted(xml_docs.keys() & pt_docs.keys()):
    x, p = xml_docs[pmid], pt_docs[pmid]
    if x.text != p.text:
        i = next((k for k, (a, b) in enumerate(zip(x.text, p.text)) if a != b), min(len(x.text), len(p.text)))
        problems.append(f"{pmid}: text differs at char {i}")
    if {k: e.type for k, e in x.entities.items()} != {k: e.type for k, e in p.entities.items()}:
        problems.append(f"{pmid}: entity IDs or types differ")
    for k in x.entities.keys() & p.entities.keys():
        if {(m.start, m.end) for m in x.entities[k].mentions} != {(m.start, m.end) for m in p.entities[k].mentions}:
            problems.append(f"{pmid}: mention spans differ for {k}")
    if set(x.relations) != set(p.relations):
        problems.append(f"{pmid}: relations differ")
print(f"compared {len(xml_docs.keys() & pt_docs.keys())} docs, {len(problems)} problems")
for line in problems[:20]:
    print(" ", line)
sys.exit(1 if problems else 0)