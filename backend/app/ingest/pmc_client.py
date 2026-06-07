"""PubMed Central — full-text XML via E-utilities efetch."""

import re
from datetime import UTC, datetime

import httpx
from lxml import etree

from app.logging import get_logger
from app.models import Author, Paper, PaperSource, Reference, Section

log = get_logger(__name__)

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def parse_pmc_id(s: str) -> str | None:
    s = s.strip()
    m = re.search(r"PMC\d+", s, re.IGNORECASE)
    if m:
        return m.group(0).upper()
    if s.startswith("pmc:"):
        return s[4:].upper()
    return None


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

    method_sections = []
    for sec in article.findall(".//sec"):
        title_node = sec.find("title")
        if title_node is None:
            continue
        sec_title = (title_node.text or "").strip().lower()
        if any(k in sec_title for k in ["method", "material", "experimental"]):
            if any(ancestor in method_sections for ancestor in sec.iterancestors("sec")):
                continue
            method_sections.append(sec)
    methods_text_parts = ["".join(sec.itertext()).strip() for sec in method_sections]
    if methods_text_parts:
        sections["methods"] = Section(name="methods", text="\n\n".join(methods_text_parts))

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
