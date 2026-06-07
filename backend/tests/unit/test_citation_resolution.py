from app.agent.tools.paper_fetch import _citation_matches_title
from app.ingest.crossref_client import _citation_contains_title


def test_citation_title_identity_requires_substantial_overlap():
    citation = (
        "Jackson HW et al. The single-cell pathology landscape of breast cancer. "
        "Nature 578, 615-620 (2020)."
    )
    title = "The single-cell pathology landscape of breast cancer"

    assert _citation_matches_title(citation, title)
    assert _citation_contains_title(citation, title)
    assert not _citation_matches_title(citation, "Unrelated protein folding methods")
