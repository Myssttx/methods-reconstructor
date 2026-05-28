"""Verify the fixture chain can be looked up by realistic citation strings."""

from app.ingest.fixtures import list_fixture_ids, try_load_fixture


def test_fixtures_present():
    ids = list_fixture_ids()
    assert "fixture:paper_a" in ids
    assert "fixture:bremer_2021" in ids
    assert "fixture:okamoto_2016" in ids


def test_load_by_exact_paper_id():
    p = try_load_fixture("fixture:bremer_2021")
    assert p is not None
    assert p.paper_id == "fixture:bremer_2021"


def test_load_by_author_year_citation():
    p = try_load_fixture("Bremer et al., 2021. Dissociation protocols for cortical scRNA-seq.")
    assert p is not None
    assert p.paper_id == "fixture:bremer_2021"


def test_load_by_title_substring():
    p = try_load_fixture("dissociation protocols for cortical scrna-seq")
    assert p is not None
    assert p.paper_id == "fixture:bremer_2021"
