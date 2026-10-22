# Evaluation protocol

## Metrics
BC8 BioRED Subtask 1 metrics, micro-F1 = 2TP / (2TP + FP + FN), summed over all documents.
A relation is an unordered entity-ID pair; "None" is never a prediction.

| Level | Match requires | Role |
|---|---|---|
| pair | ID pair | context |
| pair + type | pair and relation type | **primary metric** |
| pair + novelty | pair and Novel/No | EVAL.md only |
| pair + type + novelty | all three | novelty column |
| macro-F1 | pair+type F1 per relation type, averaged over types present in the scored gold | macro column |

Macro-F1 averages 8 types on dev and 7 on test (no Drug_Interaction), so dev and test macro values are not comparable. Dev macro-F1 swings on single relations (Conversion n=1, Drug_Interaction n=2); do not tune on it.

## Scorer
`biored.eval` (check scorer) matches NCBI's `run_biored_eval.py` from `biored_re_source_code.tar`
on the BC8 FTP folder (SHA-256 74d71f00df3faf63d82418784f6f8a8543fb321df442237f3074ac584cc33021,
not redistributed). Like the official script it skips Disease–Disease, Gene–Variant and
Gene–OrganismTaxon relations in gold and predictions.

Agreement on dev (100 docs, 1,163 gold relations): identical TP/FP/FN at all four levels on
11 controlled prediction sets (`scripts/check_scorers.py`, `results/runs/scorer_agreement.json`)
and on the Phase 4 baseline. `score(gold, gold)` = 1.0 for every metric.

## Test scoring
The official script cannot read the test gold (direction lines, relation IDs with no mention),
so test scores come from `biored.eval`. It scores 6,035 gold relations; the 17 that no
pair-based model can predict count as false negatives (recall ceiling 0.9972).
Final test predictions are also submitted to the BC8 post-task CodaLab Test phase as an
external check; both numbers are reported.

All predictions pass `validate_preds()` before scoring. Test is scored once per final system,
after models and prompts are frozen.

## Uncertainty
Paired bootstrap over abstracts: 10,000 resamples, seed 0, 95% percentile intervals.
Models are compared on the same resampled abstracts.

## Headline comparisons (fixed before any test results)
Primary metric on test, paired bootstrap:
1. Best encoder (chosen on dev) vs Claude Haiku
2. Best encoder vs Claude Sonnet
3. Best encoder vs Claude Opus

Three comparisons: report 98.3% intervals (Bonferroni) alongside the 95% ones.
Everything else is exploratory, including Qwen, thinking settings, per-type F1, the
learning curve, and the PMID < 36,000,000 vs ≥ 36,000,000 contamination split.

## Dev-set precision
A near-trivial predictor (every candidate pair = Association/Novel) gets dev pair+type F1 0.155,
95% CI [0.121, 0.193]. With 100 abstracts, dev differences of a few points are not evidence;
use dev for choosing, test for claims.
