"""End-to-end ingest: identifier → Paper → Elastic.

Resolution order:
  - looks like arxiv id / URL → arXiv API
  - looks like PMC id           → PMC E-utilities
  - looks like DOI              → OpenAlex (then Crossref fallback)
  - else                        → try arXiv, then PMC, then DOI heuristic

The pipeline indexes the resulting Paper into Elastic (papers index) with
sentence-level vectors for the methods section.
"""

import re
from datetime import UTC, datetime

from app.ingest import arxiv_client, openalex_client, pmc_client
from app.ingest.fixtures import try_load_fixture
from app.llm.embeddings import embed_texts
from app.logging import get_logger
from app.models import Paper, PaperSource, Section
from app.search.papers_dao import index_paper

log = get_logger(__name__)


SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    return sentences


def stamp_sentence_ids(text: str) -> tuple[str, list[str]]:
    """Return (text_with_[N]_prefixes, list_of_sentences)."""
    sents = split_sentences(text)
    stamped = "\n".join(f"[{i}] {s}" for i, s in enumerate(sents))
    return stamped, sents


async def ingest_identifier(identifier: str) -> Paper | None:
    """Resolve the user's input string to a Paper and index it."""
    fixture = try_load_fixture(identifier)
    if fixture is not None:
        log.info("ingest.fixture", paper_id=fixture.paper_id)
        return await _index_with_sentences(fixture)

    arxiv_id = arxiv_client.parse_arxiv_id(identifier)
    if arxiv_id:
        paper = arxiv_client.fetch_arxiv(arxiv_id)
        if paper:
            return await _index_with_sentences(paper)

    pmc_id = pmc_client.parse_pmc_id(identifier)
    if pmc_id:
        paper = await pmc_client.fetch_pmc(pmc_id)
        if paper:
            return await _index_with_sentences(paper)

    doi = openalex_client.parse_doi(identifier)
    if doi:
        meta = await openalex_client.fetch_openalex_by_doi(doi)
        if meta:
            paper = _paper_from_openalex(doi, meta)
            return await _index_with_sentences(paper)

    log.warning("ingest.unresolved", identifier=identifier)
    return None


def _paper_from_openalex(doi: str, meta: dict) -> Paper:
    from app.models import Author, Reference

    abstract_inverted = meta.get("abstract_inverted_index") or {}
    abstract = _rebuild_abstract(abstract_inverted) if abstract_inverted else ""

    refs = []
    for i, ref in enumerate(meta.get("referenced_works", []), start=1):
        # OpenAlex returns work URLs like https://openalex.org/W123 — keep raw
        refs.append(Reference(ref_id=f"ref_{i}", raw_citation=ref, doi=None, resolved=False))

    authors = [
        Author(name=a.get("author", {}).get("display_name", ""))
        for a in meta.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]

    sections: dict[str, Section] = {}
    if abstract:
        sections["abstract"] = Section(name="abstract", text=abstract)

    return Paper(
        paper_id=f"doi:{doi}",
        source=PaperSource.OPENALEX,
        title=meta.get("title") or doi,
        authors=authors,
        year=meta.get("publication_year"),
        venue=(meta.get("primary_location") or {}).get("source", {}).get("display_name"),
        abstract=abstract,
        sections=sections,
        references=refs,
        open_access_url=(meta.get("open_access") or {}).get("oa_url"),
        full_text_available=False,
        ingested_at=datetime.now(UTC).isoformat(),
    )


def _rebuild_abstract(inverted: dict[str, list[int]]) -> str:
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


async def _index_with_sentences(paper: Paper) -> Paper:
    methods = paper.methods_text()
    if methods:
        stamped, sents = stamp_sentence_ids(methods)
        # Keep the stamped form in sections so later prompts can reference [N] ids.
        paper.sections["methods"] = Section(name="methods", text=stamped)
        vectors = embed_texts(sents) if sents else []
        sentence_docs = [
            {"sentence_id": i, "text": s, "vector": v}
            for i, (s, v) in enumerate(zip(sents, vectors, strict=False))
        ]
    else:
        sentence_docs = []

    await index_paper(paper, sentence_docs)
    return paper
