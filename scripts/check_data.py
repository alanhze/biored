"""scripts/check_data.py"""
import argparse
import sys
from collections import Counter

from biored.data import allowed_type_pairs, candidate_pairs, load_config, load_splits

# (docs, mention lines, relations) from DATA_CARD.md section 2
EXPECTED = {"train": (500, 16_884, 5_340), "dev": (100, 3_535, 1_163), "test": (400, 15_404, 6_036)}
# Exceptions already explained in DATA_CARD.md section 5
KNOWN_MISSING = {"train": 0, "dev": 0, "test": 3}

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
    missing = [(d.pmid, r) for d in docs for r in d.relations
               if r.e1 not in d.entities or r.e2 not in d.entities]
    dups = sum(len(d.relations) - len({r.key for r in d.relations}) for d in docs)
    bad_spans = [(d.pmid, m.start, m.end, m.text, d.text[m.start:m.end])
                 for d in docs for e in d.entities.values() for m in e.mentions
                 if d.text[m.start:m.end] != m.text]
    reach = n_cand = type_blocked = 0
    blocked_examples = []
    for d in docs:
        cands = set(candidate_pairs(d, allowed))
        n_cand += len(cands)
        for r in d.relations:
            if r.key in cands:
                reach += 1
            elif r.e1 in d.entities and r.e2 in d.entities:
                type_blocked += 1
                blocked_examples.append((d.pmid, r.type, d.entities[r.e1].type, d.entities[r.e2].type))
    warn = Counter(w.split("\t")[0] for d in docs for w in d.warnings)
    n_dir = sum(len(d.directions) for d in docs)

    print(f"\n## {name}")
    print(f"docs={len(docs)} mention_lines={n_ment} entities={sum(len(d.entities) for d in docs)} "
          f"rels={n_rel} direction_lines={n_dir}")
    print(f"missing_endpoints={len(missing)} type_pair_not_in_train={type_blocked} dup_pairs={dups} "
          f"span_mismatches={len(bad_spans)}")
    print(f"recall_ceiling={reach / max(n_rel, 1):.4f} ({reach}/{n_rel}) candidates={n_cand} "
          f"positive_share={n_rel / max(n_cand, 1):.3f}")
    print("  types:", Counter(r.type for d in docs for r in d.relations).most_common())
    print("  novelty:", dict(Counter(r.novel for d in docs for r in d.relations)))
    print("  entity types:", dict(Counter(e.type for d in docs for e in d.entities.values())))
    print("  warnings:", dict(warn) or "none")
    if missing:
        print("  missing endpoints:", missing[:5])
    if blocked_examples:
        print("  type pair not in train:", blocked_examples[:5])
    if bad_spans:
        print("  first span mismatches (pmid, start, end, file text, doc text):", bad_spans[:3])

    if (len(docs), n_ment, n_rel) != EXPECTED[name]:
        failures.append(f"{name}: counts {(len(docs), n_ment, n_rel)} != expected {EXPECTED[name]}")
    if len(missing) != KNOWN_MISSING[name]:
        failures.append(f"{name}: {len(missing)} missing endpoints, data card lists {KNOWN_MISSING[name]}")
    if bad_spans:
        failures.append(f"{name}: {len(bad_spans)} mention offsets don't match the text")

print("\n" + ("ALL CHECKS PASSED" if not failures else "FAILED:\n  " + "\n  ".join(failures)))
sys.exit(1 if failures else 0)
