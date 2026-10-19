from collections import Counter
import yaml
from biored.data import load_splits, allowed_type_pairs, candidate_pairs

splits = load_splits(yaml.safe_load(open("configs/data.yaml")))
allowed = allowed_type_pairs(splits["train"])
print("allowed type pairs:", sorted(allowed))
for name, docs in splits.items():
    n_rel = sum(len(d.relations) for d in docs)
    missing = [(d.pmid, r) for d in docs for r in d.relations
               if r.e1 not in d.entities or r.e2 not in d.entities]
    dups = sum(len(d.relations) - len({r.key for r in d.relations}) for d in docs)
    reach = n_cand = 0
    for d in docs:
        cands = set(candidate_pairs(d, allowed))
        n_cand += len(cands)
        reach += sum(r.key in cands for r in d.relations)
    print(f"{name}: docs={len(docs)} rels={n_rel} missing_endpoints={len(missing)} dup_pairs={dups} "
          f"recall_ceiling={reach / max(n_rel, 1):.3f} candidates={n_cand} positive_share={n_rel / max(n_cand, 1):.3f}")
    print("  types:", Counter(r.type for d in docs for r in d.relations).most_common())
    print("  novelty:", Counter(r.novel for d in docs for r in d.relations))
    print("  first missing:", missing[:3])
