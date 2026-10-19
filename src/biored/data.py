from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

REL_TYPES = ["Association", "Positive_Correlation", "Negative_Correlation", "Bind",
             "Cotreatment", "Comparison", "Drug_Interaction", "Conversion"]
NOVELTY = ["No", "Novel"]

@dataclass
class Mention:
    start: int   # character offsets into Doc.text
    end: int
    text: str

@dataclass
class Entity:
    id: str
    type: str
    mentions: list[Mention] = field(default_factory=list)

@dataclass(frozen=True)
class Relation:
    e1: str
    e2: str
    type: str
    novel: str   # "Novel" or "No"

    @property
    def key(self) -> tuple[str, str]:
        return tuple(sorted((self.e1, self.e2)))

@dataclass
class Doc:
    pmid: str
    text: str
    entities: dict[str, Entity]
    relations: list[Relation]
    title_end: int = 0

def split_ids(raw: str) -> list[str]:
    """One mention can carry several IDs, e.g. 'D001,D002'. Check variant IDs before trusting this."""
    return [x.strip() for x in raw.split(",") if x.strip() and x.strip() != "-"]

def _add_mention(entities, raw_id, etype, start, end, text):
    for eid in split_ids(raw_id):
        ent = entities.setdefault(eid, Entity(eid, etype))
        if all((m.start, m.end) != (start, end) for m in ent.mentions):
            ent.mentions.append(Mention(start, end, text))

def load_bioc_xml(path: str | Path) -> list[Doc]:
    from bioc import biocxml   # imported here so the serving image doesn't need bioc
    with open(path, encoding="utf-8") as fp:
        collection = biocxml.load(fp)
    docs = []
    for d in collection.documents:
        size = max(p.offset + len(p.text or "") for p in d.passages)
        chars = [" "] * size
        for p in d.passages:
            chars[p.offset:p.offset + len(p.text or "")] = list(p.text or "")
        entities: dict[str, Entity] = {}
        for p in d.passages:
            for a in p.annotations:
                for loc in a.locations:
                    _add_mention(entities, a.infons.get("identifier", ""), a.infons.get("type", ""),
                                 loc.offset, loc.offset + loc.length, a.text)
        raw = list(d.relations) + [r for p in d.passages for r in p.relations]
        # Print one r.infons first to confirm these key names in your files.
        rels = [Relation(r.infons["entity1"], r.infons["entity2"], r.infons["type"],
                         r.infons.get("novel", "No")) for r in raw]
        docs.append(Doc(d.id, "".join(chars), entities, rels, len(d.passages[0].text or "")))
    return docs

def load_pubtator(path: str | Path) -> list[Doc]:
    docs = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8").strip()):
        lines = block.splitlines()
        pmid, _, title = lines[0].split("|", 2)
        abstract = lines[1].split("|", 2)[2] if len(lines) > 1 and "|a|" in lines[1] else ""
        entities: dict[str, Entity] = {}
        rels = []
        for line in lines[2:]:
            f = line.split("\t")
            if len(f) >= 6 and f[1].isdigit():        # PMID start end mention type id
                _add_mention(entities, f[5], f[4], int(f[1]), int(f[2]), f[3])
            elif len(f) >= 5:                          # PMID type id1 id2 novelty [extra columns]
                rels.append(Relation(f[2], f[3], f[1], f[4]))
        docs.append(Doc(pmid, f"{title} {abstract}", entities, rels, len(title)))
    return docs

def load_any(path: str | Path) -> list[Doc]:
    return load_bioc_xml(path) if str(path).lower().endswith(".xml") else load_pubtator(path)

def load_splits(paths: dict[str, list[str]]) -> dict[str, list[Doc]]:
    splits = {name: [d for p in files for d in load_any(p)] for name, files in paths.items()}
    seen: dict[str, str] = {}
    for name, docs in splits.items():
        for d in docs:
            assert d.pmid not in seen, f"{d.pmid} is in both {seen[d.pmid]} and {name}"
            seen[d.pmid] = name
    return splits

def type_combo(doc: Doc, a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((doc.entities[a].type, doc.entities[b].type)))

def allowed_type_pairs(train: list[Doc]) -> set[tuple[str, str]]:
    return {type_combo(d, r.e1, r.e2) for d in train for r in d.relations
            if r.e1 in d.entities and r.e2 in d.entities}

def candidate_pairs(doc: Doc, allowed: set[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(a, b) for a, b in combinations(sorted(doc.entities), 2)
            if type_combo(doc, a, b) in allowed]

_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")

def sentence_spans(doc: Doc) -> list[tuple[int, int]]:
    """Rough splitter, title kept as its own sentence. Good enough for error analysis."""
    spans, start = [(0, doc.title_end)], doc.title_end + 1
    for m in _SENT_END.finditer(doc.text, start):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(doc.text)))
    return spans
