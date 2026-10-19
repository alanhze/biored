"""Loader tests on a synthetic PubTator file that reproduces each quirk in DATA_CARD.md section 5.
The text is made up, so this file is safe to commit."""

import pytest

from biored.data import (
    allowed_type_pairs,
    candidate_pairs,
    load_pubtator,
    load_splits,
    split_ids,
)

TITLE = "BRCA1 variant and aspirin in cancer."
ABSTRACT = "Aspirin lowered risk. ACE2 binds virus."
# Offsets: title starts at 0, abstract at len(TITLE) + 1 = 37
FIXTURE = "\n".join(
    [
        f"111|t|{TITLE}",
        f"111|a|{ABSTRACT}",
        "111\t0\t5\tBRCA1\tGeneOrGeneProduct\t672",
        "111\t6\t13\tvariant\tSequenceVariant\tp|SUB|I|61|Q",
        "111\t18\t25\taspirin\tChemicalEntity\tD001241",
        "111\t29\t35\tcancer\tDiseaseOrPhenotypicFeature\tD009369;D001943",
        "111\t37\t44\tAspirin\tChemicalEntity\tD001241",
        "111\t59\t63\tACE2\tGeneOrGeneProduct\t59272",
        "111\t70\t75\tvirus\tOrganism\t2697049",
        "111\tAssociation\t672\tD009369\tNovel",
        "111\tNegative_Correlation\tD001241\tD009369\tNo",
        "111\tPositive_Correlation\tp|SUB|I|61|Q\tD001943\tNovel",
        "111\tBind\t59272\t2697049\tNovel",
        "111\tAssociation\tC999999\t672\tNo",  # endpoint with no mention
        "111\tBind\t672\t672\tNo",  # self-relation
        "111\tAssociation\t-\t672\tNo",  # "-" endpoint
        "111\tp|SUB|I|61|Q\tD001943\tSubject:p|SUB|I|61|Q",  # 4-field direction line
        "",
        "222|t|Second title.",
        "222|a|",
        "222\t0\t6\tSecond\tChemicalEntity\tD000001",
    ]
)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "toy.pubtator"
    p.write_text(FIXTURE + "\n", encoding="utf-8")
    return p


def test_split_ids_keeps_variant_pipes():
    assert split_ids("D1,D2; D3") == ["D1", "D2", "D3"]
    assert split_ids("p|SUB|I|61|Q") == ["p|SUB|I|61|Q"]
    assert split_ids("-") == []


def test_counts_and_direction_line(path):
    docs = load_pubtator(path)
    assert [d.pmid for d in docs] == ["111", "222"]
    d = docs[0]
    assert d.n_mention_lines == 7
    assert len(d.relations) == 7  # direction line is not a relation
    assert d.directions == [("p|SUB|I|61|Q", "D001943", "Subject:p|SUB|I|61|Q")]
    assert d.warnings == ["self_relation\t672"]


def test_dash_is_not_an_entity(path):
    d = load_pubtator(path)[0]
    assert "-" not in d.entities
    assert any(r.e1 == "-" for r in d.relations)  # gold kept, unreachable


def test_offsets_line_up(path):
    for d in load_pubtator(path):
        for e in d.entities.values():
            for m in e.mentions:
                assert d.text[m.start : m.end] == m.text


def test_multi_id_mention_and_dedup(path):
    d = load_pubtator(path)[0]
    assert "D009369" in d.entities and "D001943" in d.entities
    assert len(d.entities["D001241"].mentions) == 2  # same chemical, two spans


def test_organism_normalized(path):
    assert load_pubtator(path)[0].entities["2697049"].type == "OrganismTaxon"


def test_missing_endpoint_kept(path):
    d = load_pubtator(path)[0]
    assert any(r.e1 == "C999999" for r in d.relations)
    assert "C999999" not in d.entities


def test_pairs_unordered_and_candidates(path):
    docs = load_pubtator(path)
    allowed = allowed_type_pairs(docs)
    assert ("GeneOrGeneProduct", "OrganismTaxon") in allowed
    cands = set(candidate_pairs(docs[0], allowed))
    for r in docs[0].relations:
        if r.e1 in docs[0].entities and r.e2 in docs[0].entities and r.e1 != r.e2:
            assert r.key in cands


def test_split_overlap_assert(path):
    with pytest.raises(AssertionError, match="is in both"):
        load_splits({"train": [str(path)], "dev": [str(path)]})
