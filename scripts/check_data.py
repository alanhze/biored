"""Load every split through biored.data and check it against the Phase 1 counts.

Exit code 1 if a count differs from DATA_CARD.md or an offset doesn't line up with the text.
Usage: python scripts/check_data.py [--config configs/data.yaml] [--root DIR]
"""
import argparse
import sys
from collections import Counter

from biored.data import allowed_type_pairs, candidate_pairs, load_config, load_splits

# (docs, mention lines, relations) from DATA_CARD.md section 2
EXPECTED = {"train": (500, 16_884, 5_340), "dev": (100, 3_535, 1_163), "test": (400, 15_404, 6_036)}
# Gold relations no pair-based model can predict, by reason (DATA_CARD.md section 5):
#   dash_endpoint  an argument is "-" (mention annotated without a normalized ID)
#   no_mention     an argument ID that no mention in the document carries
#   self_relation  e1 == e2, e.g. a protein binding itself; candidate pairs are distinct IDs
#   type_pair      both ends exist but their type pair never occurs in train
KNOWN_UNREACHABLE = {
    "train": {"self_relation": 4},
    "dev": {},
    "test": {"dash_endpoint": 10, "no_mention": 3, "self_relation": 4, "type_pair": 1},
}


def unreachable_reason(d, r, cands):
    if "-" in (r.e1, r.e2):
        return "dash_endpoint"
    if r.e1 not in d.entities or r.e2 not in d.entities:
        return "no_mention"
    if r.e1 == r.e2:
        return "self_relation"
    if r.key not in cands:
        return "type_pair"
    return None

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="configs/data.yaml")
ap.add_argument("--root", default=None)
args = ap.parse_args()

splits = load_splits(load_config(args.config, args.root))
print("split-overlap assert: passed")
allowed = allowed_type_pairs(splits["train"])
print("allowed type pairs:", len(allowed))
for a, b in sorted(allowed):
    print(f"  {a}–{b}")

failures = []
for name, docs in splits.items():
    n_rel = sum(len(d.relations) for d in docs)
    n_ment = sum(d.n_mention_lines for d in docs)
    dups = sum(len(d.relations) - len({r.key for r in d.relations}) for d in docs)
    bad_spans = [(d.pmid, m.start, m.end, m.text, d.text[m.start:m.end])
                 for d in docs for e in d.entities.values() for m in e.mentions
                 if d.text[m.start:m.end] != m.text]
    reach = n_cand = 0
    unreachable = []   # (reason, pmid, relation)
    for d in docs:
        cands = set(candidate_pairs(d, allowed))
        n_cand += len(cands)
        for r in d.relations:
            why = unreachable_reason(d, r, cands)
            if why:
                unreachable.append((why, d.pmid, r))
            else:
                reach += 1
    by_reason = dict(Counter(u[0] for u in unreachable))
    warn = Counter(w.split("\t")[0] for d in docs for w in d.warnings)
    n_dir = sum(len(d.directions) for d in docs)

    print(f"\n## {name}")
    print(f"docs={len(docs)} mention_lines={n_ment} entities={sum(len(d.entities) for d in docs)} "
          f"rels={n_rel} direction_lines={n_dir}")
    print(f"unreachable_gold={len(unreachable)} {by_reason or ''} dup_pairs={dups} "
          f"span_mismatches={len(bad_spans)}")
    print(f"recall_ceiling={reach / max(n_rel, 1):.4f} ({reach}/{n_rel}) candidates={n_cand} "
          f"positive_share={n_rel / max(n_cand, 1):.3f}")
    print("  types:", Counter(r.type for d in docs for r in d.relations).most_common())
    print("  novelty:", dict(Counter(r.novel for d in docs for r in d.relations)))
    print("  entity types:", dict(Counter(e.type for d in docs for e in d.entities.values())))
    print("  warnings:", dict(warn) or "none")
    for why, pmid, r in unreachable:   # IDs and labels only, safe to paste into the data card
        print(f"  UNREACHABLE\t{why}\t{pmid}\t{r.type}\t{r.e1}\t{r.e2}\t{r.novel}")
    if bad_spans:
        print("  first span mismatches (pmid, start, end, file text, doc text):", bad_spans[:3])

    if (len(docs), n_ment, n_rel) != EXPECTED[name]:
        failures.append(f"{name}: counts {(len(docs), n_ment, n_rel)} != expected {EXPECTED[name]}")
    if by_reason != KNOWN_UNREACHABLE[name]:
        failures.append(f"{name}: unreachable gold {by_reason}, expected {KNOWN_UNREACHABLE[name]}")
    if bad_spans:
        failures.append(f"{name}: {len(bad_spans)} mention offsets don't match the text")

print("\n" + ("ALL CHECKS PASSED" if not failures else "FAILED:\n  " + "\n  ".join(failures)))
sys.exit(1 if failures else 0)