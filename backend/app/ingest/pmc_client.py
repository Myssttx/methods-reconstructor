"""PubMed Central — full-text XML via E-utilities efetch."""

import copy
import re
from datetime import UTC, datetime

import httpx
from lxml import etree

from app.logging import get_logger
from app.models import Author, Paper, PaperSource, Reference, Section

log = get_logger(__name__)

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
IDCONV = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"


def parse_pmc_id(s: str) -> str | None:
    s = s.strip()
    m = re.search(r"PMC\d+", s, re.IGNORECASE)
    if m:
        return m.group(0).upper()
    if s.startswith("pmc:"):
        return s[4:].upper()
    return None


async def find_pmc_by_doi(doi: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                IDCONV,
                params={
                    "ids": doi,
                    "format": "json",
                    "tool": "methods-reconstructor",
                },
            )
            response.raise_for_status()
            records = response.json().get("records") or []
    except Exception as error:
        log.warning("pmc.idconv_failed", doi=doi, error=str(error))
        return None
    pmc_id = str((records[0] if records else {}).get("pmcid") or "")
    return pmc_id.upper() or None


async def fetch_pmc(pmc_id: str) -> Paper | None:
    pmc_id = pmc_id.replace("PMC", "")
    params = {"db": "pmc", "id": pmc_id, "rettype": "xml"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(EFETCH, params=params)
            resp.raise_for_status()
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
        ingested_at=datetime.now(UTC).isoformat(),
    )


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
