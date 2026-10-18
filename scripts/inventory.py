# scripts/inventory.py
import re
from pathlib import Path

for p in sorted(Path("data/raw").rglob("*")):
    if p.suffix.lower() == ".xml":
        s = p.read_text(encoding="utf-8", errors="ignore")
        print(f"{p}: docs={s.count('<document>')} mentions={s.count('<annotation')} relations={s.count('<relation')}")
    elif p.suffix.lower() in {".pubtator", ".txt"}:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        docs = sum(bool(re.match(r"^\S+\|t\|", l)) for l in lines)
        rels = sum(l.count("\t") >= 4 and not l.split("\t")[1].isdigit() for l in lines)
        print(f"{p}: docs={docs} relations={rels}")