from __future__ import annotations
"""PubMed Central — full-text XML via E-utilities efetch."""

import asyncio
import copy
import re
from datetime import timezone, datetime
from time import monotonic

import httpx
from lxml import etree

from app.config import get_settings
from app.logging import get_logger
from app.models import Author, Paper, PaperSource, Reference, Section

log = get_logger(__name__)

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 4
_request_lock = asyncio.Lock()
_last_request_at = 0.0


def parse_pmc_id(s: str) -> str | None:
    s = s.strip()
    m = re.search(r"PMC\d+", s, re.IGNORECASE)
    if m:
        return m.group(0).upper()
    if s.startswith("pmc:"):
        return s[4:].upper()
    return None


async def find_pmc_by_doi(doi: str) -> str | None:
    settings = get_settings()
    params = {
        "ids": doi,
        "format": "json",
        "tool": "methods-reconstructor",
    }
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    try:
        response = await _get_with_retry(IDCONV, params=params, timeout=20.0)
        records = response.json().get("records") or []
    except Exception as error:
        log.warning("pmc.idconv_failed", doi=doi, error=str(error))
        return None
    pmc_id = str((records[0] if records else {}).get("pmcid") or "")
    return pmc_id.upper() or None


async def fetch_pmc(pmc_id: str) -> Paper | None:
    pmc_id = pmc_id.replace("PMC", "")
    settings = get_settings()
    params = {
        "db": "pmc",
        "id": pmc_id,
        "rettype": "xml",
        "retmode": "xml",
        "tool": "methods-reconstructor",
    }
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    try:
        resp = await _get_with_retry(EFETCH, params=params, timeout=30.0)
    except Exception as e:
        log.warning("pmc.fetch_failed", pmc_id=pmc_id, error=str(e))
        return None

    try:
        root = etree.fromstring(resp.content)
    except etree.XMLSyntaxError as e:
        log.warning("pmc.parse_failed", pmc_id=pmc_id, error=str(e))
        return None

    article = root.find(".//article")
    if article is None:
        return None

    title_el = article.find(".//article-title")
    title = "".join(title_el.itertext()).strip() if title_el is not None else f"PMC{pmc_id}"

    authors = [
        Author(
            name=" ".join(
                t.strip() for t in [(c.findtext("given-names") or ""), (c.findtext("surname") or "")] if t.strip()
            )
        )
        for c in article.findall(".//contrib[@contrib-type='author']/name")
        if (c.findtext("surname") or c.findtext("given-names"))
    ]

    abstract_el = article.find(".//abstract")
    abstract = "".join(abstract_el.itertext()).strip() if abstract_el is not None else ""

    sections: dict[str, Section] = {}
    if abstract:
        sections["abstract"] = Section(name="abstract", text=abstract)

    methods_text = _extract_methods_text(article)
    if methods_text:
        sections["methods"] = Section(name="methods", text=methods_text)

    references: list[Reference] = []
    for i, ref in enumerate(article.findall(".//ref"), start=1):
        rid = ref.get("id") or f"ref_{i}"
        raw = "".join(ref.itertext()).strip()
        doi_el = ref.find(".//pub-id[@pub-id-type='doi']")
        references.append(
            Reference(
                ref_id=rid,
                raw_citation=raw,
                doi=(doi_el.text if doi_el is not None else None),
                resolved=doi_el is not None,
            )
        )

    year_el = article.find(".//pub-date/year")
    year = int(year_el.text) if (year_el is not None and year_el.text and year_el.text.isdigit()) else None

    return Paper(
        paper_id=f"pmc:PMC{pmc_id}",
        source=PaperSource.PMC,
        title=title,
        authors=authors,
        year=year,
        venue="PubMed Central",
        abstract=abstract,
        sections=sections,
        references=references,
        full_text_available="methods" in sections,
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )


async def _get_with_retry(
    url: str,
    *,
    params: dict[str, str],
    timeout: float,
) -> httpx.Response:
    """Respect NCBI request limits and retry transient failures."""
    settings = get_settings()
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        await _wait_for_request_slot(has_api_key=bool(settings.ncbi_api_key))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
            if response.status_code not in _RETRYABLE_STATUS:
                response.raise_for_status()
                return response
            last_error = httpx.HTTPStatusError(
                f"Transient PMC HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else 2**attempt
            log.warning(
                "pmc.retry",
                attempt=attempt + 1,
                status=response.status_code,
                delay_seconds=delay,
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            last_error = error
            delay = 2**attempt
            log.warning(
                "pmc.retry",
                attempt=attempt + 1,
                error=type(error).__name__,
                delay_seconds=delay,
            )
        if attempt < _MAX_RETRIES - 1:
            await asyncio.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("PMC request failed without a response")


async def _wait_for_request_slot(*, has_api_key: bool) -> None:
    """Serialize requests at NCBI's documented 3/s or 10/s limit."""
    global _last_request_at
    minimum_interval = 0.11 if has_api_key else 0.34
    async with _request_lock:
        wait_seconds = minimum_interval - (monotonic() - _last_request_at)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        _last_request_at = monotonic()


def _extract_methods_text(article: etree._Element) -> str:
    method_sections: list[etree._Element] = []
    for section in article.findall(".//sec"):
        title_node = section.find("title")
        if title_node is None:
            continue
        section_title = _render_text(title_node).casefold()
        if any(
            keyword in section_title
            for keyword in ["method", "material", "experimental"]
        ):
            if any(ancestor in method_sections for ancestor in section.iterancestors("sec")):
                continue
            method_sections.append(section)

    parts: list[str] = []
    for section in method_sections:
        for node in section.iter():
            local_name = etree.QName(node).localname
            if local_name not in {"title", "p"}:
                continue
            if _has_excluded_ancestor(node, section):
                continue
            text = _render_text(node)
            if text:
                parts.append(text)
    return "\n".join(parts)


def _has_excluded_ancestor(
    node: etree._Element,
    boundary: etree._Element,
) -> bool:
    excluded = {"fig", "table-wrap", "supplementary-material"}
    for ancestor in node.iterancestors():
        if ancestor is boundary:
            return False
        if etree.QName(ancestor).localname in excluded:
            return True
    return False


def _render_text(node: etree._Element) -> str:
    rendered = copy.deepcopy(node)
    for citation in rendered.xpath(".//xref[@ref-type='bibr']"):
        reference_id = (citation.get("rid") or "").split()[0].lstrip("#")
        if reference_id:
            citation.text = f"[{reference_id}]"
            for child in list(citation):
                citation.remove(child)
    return " ".join("".join(rendered.itertext()).split())
