"""Scorer tests on a synthetic PubTator file (made-up text, safe to commit).

Document 111 has three scorable gold relations plus one GeneOrGeneProduct-SequenceVariant
relation that BC8 does not score. Document 222 has no gold relations, so any prediction there
is a false positive. The file also has a ';' ID list and a direction line, which the writer
must clean up before the official script can read it.
"""
import dataclasses

import numpy as np
import pytest

from biored.data import load_pubtator
from biored.eval import (
    LEVELS,
    bootstrap,
    count_matrix,
    entity_types,
    pair_key,
    score,
    validate_preds,
)
from biored.official import SCRIPT, run_official, write_pubtator

FIXTURE = "\n".join([
    "111|t|BRCA1 variant and aspirin in cancer.",
    "111|a|Aspirin lowered risk. ACE2 binds virus.",
    "111\t0\t5\tBRCA1\tGeneOrGeneProduct\t672",
    "111\t6\t13\tvariant\tSequenceVariant\tp|SUB|I|61|Q",
    "111\t18\t25\taspirin\tChemicalEntity\tD001241",
    "111\t29\t35\tcancer\tDiseaseOrPhenotypicFeature\tD009369;D001943",
    "111\t37\t44\tAspirin\tChemicalEntity\tD001241",
    "111\t59\t63\tACE2\tGeneOrGeneProduct\t59272",
    "111\tAssociation\t672\tD009369\tNovel",
    "111\tNegative_Correlation\tD001241\tD009369\tNo",
    "111\tPositive_Correlation\tp|SUB|I|61|Q\tD001943\tNovel",
    "111\tAssociation\t672\tp|SUB|I|61|Q\tNo",                # Gene-Variant: not scored by BC8
    "111\tp|SUB|I|61|Q\tD001943\tSubject:p|SUB|I|61|Q",      # direction line
    "",
    "222|t|Second title.",
    "222|a|Gene 4968 and drug.",
    "222\t0\t6\tSecond\tChemicalEntity\tD000001",
    "222\t19\t23\t4968\tGeneOrGeneProduct\t4968",
]) + "\n"


def _with(r, **kw):
    return r._replace(**kw) if hasattr(r, "_replace") else dataclasses.replace(r, **kw)


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "gold.pubtator"
    path.write_text(FIXTURE, encoding="utf-8")
    docs = load_pubtator(path)
    gold = {d.pmid: list(d.relations) for d in docs}
    return path, docs, gold, entity_types(docs)


def _preds(gold):
    r1, r2, r3, _ = gold["111"]
    return {
        "111": [r1,                                        # right on every level
                _with(r2, type="Positive_Correlation"),    # wrong type
                _with(r3, novel="No"),                     # wrong novelty
                _with(r1, e1="59272", e2="D001241", type="Bind")],   # not a gold pair
        "222": [_with(r1, e1="D000001", e2="4968")],       # document without gold relations
    }


EXPECTED = {   # (tp, fp, fn), counted by hand
    "pair": (3, 2, 0),
    "pair_type": (2, 3, 1),
    "pair_novelty": (2, 3, 1),
    "pair_type_novelty": (1, 4, 2),
}


def test_gold_vs_gold_is_perfect(setup):
    _, _, gold, types = setup
    s = score(gold, gold, types)
    assert s and all(v == 1.0 for v in s.values()), s


def test_hand_counted(setup):
    _, _, gold, types = setup
    pred = _preds(gold)
    for lvl, want in EXPECTED.items():
        assert tuple(count_matrix(gold, pred, lvl, types).sum(0)) == want, lvl


def test_pair_order_none_and_excluded_pairs(setup):
    _, _, gold, types = setup
    flipped = {pm: [_with(r, e1=r.e2, e2=r.e1) for r in rs] for pm, rs in gold.items()}
    assert score(gold, flipped, types)["micro_f1_pair_type_novelty"] == 1.0
    r1 = gold["111"][0]
    junk = {"111": gold["111"] + [_with(r1, e1="59272", e2="p|SUB|I|61|Q"),       # Gene-Variant
                                  _with(r1, e1="59272", e2="D001241", type="None")]}
    assert score(gold, junk, types)["micro_f1_pair_type_novelty"] == 1.0


def test_missing_document_counts_its_false_negatives(setup):
    _, _, gold, types = setup
    assert tuple(count_matrix(gold, {}, "pair", types).sum(0)) == (0, 0, 3)


def test_unknown_pmid_raises(setup):
    _, _, gold, types = setup
    with pytest.raises(KeyError):
        count_matrix(gold, {"999": gold["111"]}, "pair", types)


def test_validate_preds(setup):
    _, docs, gold, _ = setup
    validate_preds(_preds(gold), docs)
    r1 = gold["111"][0]
    for bad in ([r1, r1], [_with(r1, type="None")], [_with(r1, novel="Yes")], [_with(r1, e2="D999")]):
        with pytest.raises(ValueError):
            validate_preds({"111": bad}, docs)


def test_bootstrap(setup):
    _, _, gold, types = setup
    ca = count_matrix(gold, _preds(gold), "pair_type", types)
    b = bootstrap(ca, ca, n=2000)
    assert b["ci95"][0] <= b["f1"] <= b["ci95"][1]
    assert b["diff"] == 0 and b["diff_ci95"] == [0.0, 0.0] and b["p_two_sided"] == 1.0
    assert bootstrap(ca, n=500, seed=1) == bootstrap(ca, n=500, seed=1)


def test_writer_round_trip(setup, tmp_path):
    path, docs, gold, _ = setup
    out = tmp_path / "pred.pubtator"
    write_pubtator(path, gold, out)
    text = out.read_text(encoding="utf-8")
    assert "\n\n\n" not in text and text.endswith("\n\n")
    assert all(len(ln.split("\t")) != 4 for ln in text.splitlines())     # direction lines gone
    again = load_pubtator(out)
    assert [d.pmid for d in again] == [d.pmid for d in docs]
    for a, b in zip(docs, again):
        assert a.n_mention_lines == b.n_mention_lines
        assert {k: e.type for k, e in a.entities.items()} == {k: e.type for k, e in b.entities.items()}
        assert {(pair_key(r), r.type, r.novel) for r in a.relations} == \
               {(pair_key(r), r.type, r.novel) for r in b.relations}
        assert b.directions == []


@pytest.mark.skipif(not SCRIPT.exists(), reason="official script not in third_party/bc8_eval/")
def test_official_script_agrees(setup, tmp_path):
    path, _, gold, types = setup
    gold_clean, pred_file = tmp_path / "gold_clean.pubtator", tmp_path / "pred.pubtator"
    write_pubtator(path, gold, gold_clean)
    pred = _preds(gold)
    write_pubtator(path, pred, pred_file)
    official = run_official(gold_clean, pred_file)
    for lvl in LEVELS:
        mine = tuple(int(x) for x in count_matrix(gold, pred, lvl, types).sum(0))
        assert mine == tuple(official[lvl][k] for k in ("tp", "fp", "fn")), lvl
        assert np.isclose(official[lvl]["f1"], 2 * mine[0] / (2 * mine[0] + mine[1] + mine[2]))
