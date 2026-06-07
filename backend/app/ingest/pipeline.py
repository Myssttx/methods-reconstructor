"""End-to-end ingest: identifier → Paper → Elastic.

Resolution order:
  - looks like arxiv id / URL → arXiv API
  - looks like PMC id           → PMC E-utilities
  - looks like DOI              → OpenAlex (then Crossref fallback)
  - else                        → try arXiv, then PMC, then DOI heuristic

The pipeline indexes the resulting Paper into Elastic (papers index) with
sentence-level vectors for the methods section.
"""

import asyncio
import re
from datetime import UTC, datetime

from app.ingest import (
    arxiv_client,
    crossref_client,
    grobid_client,
    openalex_client,
    pdf_client,
    pmc_client,
    unpaywall_client,
)
from app.ingest.fixtures import try_load_fixture
from app.llm.embeddings import aembed_texts
from app.logging import get_logger
from app.models import Paper, PaperSource, Section
from app.search.papers_dao import get_paper_model, index_paper

log = get_logger(__name__)


SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
ABBREVIATION_END = re.compile(
    r"\b(?:et al|e\.g|i\.e|fig|eq|dr|mr|mrs|ms|prof|vs|no)\.$",
    re.IGNORECASE,
)
_ingest_locks: dict[str, asyncio.Lock] = {}


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # GROBID emits section headings as standalone lines.
        if len(line) < 120 and line[-1:] not in ".!?":
            continue
        for fragment in SENTENCE_SPLIT.split(line):
            fragment = fragment.strip()
            if not fragment:
                continue
            if sentences and ABBREVIATION_END.search(sentences[-1]):
                sentences[-1] = f"{sentences[-1]} {fragment}"
            else:
                sentences.append(fragment)
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
        return await _ingest_canonical(
            f"arxiv:{arxiv_id}",
            lambda: _fetch_arxiv(arxiv_id),
        )

    pmc_id = pmc_client.parse_pmc_id(identifier)
    if pmc_id:
        return await _ingest_canonical(
            f"pmc:{pmc_id}",
            lambda: pmc_client.fetch_pmc(pmc_id),
        )

    doi = openalex_client.parse_doi(identifier)
    if doi:
        return await _ingest_canonical(
            f"doi:{doi}",
            lambda: _fetch_doi(doi),
        )

    if pdf_client.is_pdf_identifier(identifier):
        paper = await _paper_from_pdf(identifier)
        if paper:
            return await _index_with_sentences(paper)

    log.warning("ingest.unresolved", identifier=identifier)
    return None


async def _ingest_canonical(
    paper_id: str,
    fetcher,
) -> Paper | None:
    lock = _ingest_locks.setdefault(paper_id, asyncio.Lock())
    async with lock:
        cached = await get_paper_model(paper_id)
        if cached and cached.methods_text():
            log.info("ingest.elastic_cache_hit", paper_id=paper_id)
            return cached
        paper = await fetcher()
        if paper is None:
            return cached
        return await _index_with_sentences(paper)


async def _fetch_arxiv(arxiv_id: str) -> Paper | None:
    paper = await asyncio.to_thread(arxiv_client.fetch_arxiv, arxiv_id)
    return await _enrich_from_open_access_pdf(paper) if paper else None


async def _fetch_doi(doi: str) -> Paper | None:
    meta = await openalex_client.fetch_openalex_by_doi(doi)
    if meta:
        paper = _paper_from_openalex(doi, meta)
    else:
        crossref = await crossref_client.fetch_crossref(doi)
        if not crossref:
            return None
        paper = _paper_from_crossref(doi, crossref)
    return await _enrich_from_open_access_pdf(paper)


async def _paper_from_pdf(identifier: str, *, paper_id: str | None = None) -> Paper | None:
    fetched = await pdf_client.fetch_pdf(identifier)
    if not fetched:
        return None
    pdf_bytes, source_url = fetched
    tei_xml = await grobid_client.process_pdf(pdf_bytes)
    if not tei_xml:
        return None
    return grobid_client.paper_from_tei(
        tei_xml,
        paper_id=paper_id or f"pdf:{source_url}",
        source_url=source_url,
    )


async def _enrich_from_open_access_pdf(paper: Paper) -> Paper:
    if paper.methods_text():
        return paper
    if paper.paper_id.startswith("doi:"):
        unpaywall_url = await unpaywall_client.find_oa_url(
            paper.paper_id.removeprefix("doi:")
        )
        paper.open_access_url = unpaywall_url or paper.open_access_url
    if not paper.open_access_url:
        return paper
    parsed = await _paper_from_pdf(paper.open_access_url, paper_id=paper.paper_id)
    if parsed is None:
        return paper

    parsed.title = paper.title or parsed.title
    parsed.authors = paper.authors or parsed.authors
    parsed.year = paper.year or parsed.year
    parsed.venue = paper.venue or parsed.venue
    parsed.abstract = paper.abstract or parsed.abstract
    parsed.source = paper.source
    if paper.abstract and "abstract" not in parsed.sections:
        parsed.sections["abstract"] = Section(name="abstract", text=paper.abstract)
    parsed.open_access_url = parsed.open_access_url or paper.open_access_url
    return parsed


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
        open_access_url=(
            (meta.get("best_oa_location") or {}).get("pdf_url")
            or (meta.get("best_oa_location") or {}).get("landing_page_url")
            or (meta.get("open_access") or {}).get("oa_url")
        ),
        full_text_available=False,
        ingested_at=datetime.now(UTC).isoformat(),
    )


def _paper_from_crossref(doi: str, meta: dict) -> Paper:
    from app.models import Author

    title_values = meta.get("title") or []
    title = title_values[0] if title_values else doi
    authors = [
        Author(name=" ".join(filter(None, [a.get("given"), a.get("family")])))
        for a in meta.get("author") or []
    ]
    date_parts = (meta.get("published") or {}).get("date-parts") or []
    year = date_parts[0][0] if date_parts and date_parts[0] else None
    return Paper(
        paper_id=f"doi:{doi}",
        source=PaperSource.CROSSREF,
        title=title,
        authors=authors,
        year=year,
        venue=(meta.get("container-title") or [None])[0],
        open_access_url=meta.get("URL"),
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
        vectors = await aembed_texts(sents) if sents else []
        sentence_docs = [
            {"sentence_id": i, "text": s, "vector": v}
            for i, (s, v) in enumerate(zip(sents, vectors, strict=False))
        ]
    else:
        sentence_docs = []

    await index_paper(paper, sentence_docs)
    return paper
