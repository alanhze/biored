from collections import Counter
from pathlib import Path

p = Path("data/raw/datasets/bioredirect/bioredirect_bc8_test.pubtator")
types, spans, ids_multi = Counter(), set(), 0
for line in p.read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) >= 6 and f[1].isdigit():
        types[f[4]] += 1
        spans.add((f[0], f[1], f[2]))
        if any(sep in f[5] for sep in (",", ";", "|")):
            ids_multi += 1
print("mention lines:", sum(types.values()))
print("unique (pmid,start,end) spans:", len(spans))
print("by type:", dict(types))
print("multi-ID mentions:", ids_multi)
