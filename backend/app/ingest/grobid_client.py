"""GROBID — PDF → structured paper content when no clean XML is available."""

import copy
import re
from datetime import UTC, datetime

import httpx
from lxml import etree

from app.config import get_settings
from app.logging import get_logger
from app.models import Author, Paper, PaperSource, Reference, Section

log = get_logger(__name__)

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}
METHOD_HEADING = re.compile(
    r"\b(method|materials?|experimental|sample preparation|data processing|image analysis)\b",
    re.IGNORECASE,
)
METHOD_BOUNDARY = re.compile(r"^(online )?(materials? and )?methods?$", re.IGNORECASE)
METHOD_STOP = re.compile(
    r"^(results?|discussion|conclusions?|references?|bibliography|extended data|"
    r"acknowledg|author contributions?|competing interests?|data availability|"
    r"additional information|supplementary)",
    re.IGNORECASE,
)
BIBLIOGRAPHY_PARAGRAPH = re.compile(
    r"^\d+\.\s+[A-Z][A-Za-z'-]+,\s+[A-Z]\.",
)


async def process_pdf(pdf_bytes: bytes) -> str | None:
    settings = get_settings()
    url = f"{settings.grobid_url}/api/processFulltextDocument"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, files={"input": ("paper.pdf", pdf_bytes, "application/pdf")})
            if resp.status_code != 200:
                log.warning("grobid.bad_status", status=resp.status_code)
                return None
            return resp.text
    except Exception as e:
        log.warning("grobid.unavailable", error=str(e))
        return None


def paper_from_tei(
    tei_xml: str,
    *,
    paper_id: str,
    source_url: str | None = None,
) -> Paper | None:
    """Parse a GROBID TEI document into the application's Paper model."""
    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        log.warning("grobid.parse_failed", error=str(e))
        return None

    title = _first_text(
        root,
        ".//tei:teiHeader//tei:titleStmt/tei:title[@level='a']",
        ".//tei:teiHeader//tei:titleStmt/tei:title",
    )
    if not title:
        title = paper_id

    authors = []
    for author in root.xpath(".//tei:teiHeader//tei:sourceDesc//tei:author", namespaces=TEI_NS):
        name = " ".join(
            part
            for part in [
                _node_text(author.find("tei:persName/tei:forename", TEI_NS)),
                _node_text(author.find("tei:persName/tei:surname", TEI_NS)),
            ]
            if part
        )
        if name and all(existing.name != name for existing in authors):
            authors.append(Author(name=name))

    abstract = _joined_paragraphs(
        root.xpath(".//tei:teiHeader//tei:profileDesc/tei:abstract", namespaces=TEI_NS)
    )
    sections: dict[str, Section] = {}
    if abstract:
        sections["abstract"] = Section(name="abstract", text=abstract)

    methods_parts: list[str] = []
    selected_divs = _method_divs(root)
    for div in selected_divs:
        heading = _first_child_text(div, "tei:head")
        body = _joined_paragraphs([div])
        if body:
            methods_parts.append(f"{heading}\n{body}" if heading else body)
    if methods_parts:
        sections["methods"] = Section(name="methods", text="\n\n".join(methods_parts))

    references = []
    for index, bibl in enumerate(
        root.xpath(".//tei:text/tei:back//tei:listBibl/*", namespaces=TEI_NS),
        start=1,
    ):
        ref_id = (
            bibl.get("{http://www.w3.org/XML/1998/namespace}id")
            or bibl.get("id")
            or f"ref_{index}"
        )
        raw = " ".join("".join(bibl.itertext()).split())
        doi_nodes = bibl.xpath(".//tei:idno[@type='DOI']/text()", namespaces=TEI_NS)
        doi = doi_nodes[0].strip() if doi_nodes else None
        title_nodes = bibl.xpath(
            ".//tei:analytic/tei:title[1] | .//tei:monogr/tei:title[1]",
            namespaces=TEI_NS,
        )
        ref_title = _node_text(title_nodes[0]) if title_nodes else None
        year_nodes = bibl.xpath(".//tei:date/@when | .//tei:date/text()", namespaces=TEI_NS)
        year_match = re.search(r"\b(19|20)\d{2}\b", year_nodes[0]) if year_nodes else None
        references.append(
            Reference(
                ref_id=ref_id,
                raw_citation=raw,
                doi=doi,
                title=ref_title,
                year=int(year_match.group(0)) if year_match else None,
                resolved=bool(doi),
            )
        )

    year_values = root.xpath(
        ".//tei:teiHeader//tei:publicationStmt/tei:date/@when"
        " | .//tei:teiHeader//tei:publicationStmt/tei:date/text()",
        namespaces=TEI_NS,
    )
    year_match = re.search(r"\b(19|20)\d{2}\b", year_values[0]) if year_values else None
    venue = _first_text(
        root,
        ".//tei:teiHeader//tei:sourceDesc//tei:monogr/tei:title",
    )

    return Paper(
        paper_id=paper_id,
        source=PaperSource.UPLOAD,
        title=title,
        authors=authors,
        year=int(year_match.group(0)) if year_match else None,
        venue=venue,
        abstract=abstract,
        sections=sections,
        references=references,
        open_access_url=source_url,
        full_text_available=bool(methods_parts),
        ingested_at=datetime.now(UTC).isoformat(),
    )


def _first_text(root: etree._Element, *paths: str) -> str:
    for path in paths:
        nodes = root.xpath(path, namespaces=TEI_NS)
        if nodes:
            text = _node_text(nodes[0])
            if text:
                return text
    return ""


def _method_divs(root: etree._Element) -> list[etree._Element]:
    top_level = root.xpath(".//tei:text/tei:body/tei:div", namespaces=TEI_NS)
    for index, div in enumerate(top_level):
        heading = _first_child_text(div, "tei:head")
        if not METHOD_BOUNDARY.match(heading):
            continue

        if div.xpath("./tei:div", namespaces=TEI_NS):
            return [div]

        selected = []
        for candidate in top_level[index:]:
            candidate_heading = _first_child_text(candidate, "tei:head")
            if selected and METHOD_STOP.match(candidate_heading):
                break
            selected.append(candidate)
        return selected

    matched = []
    for div in root.xpath(".//tei:text/tei:body//tei:div", namespaces=TEI_NS):
        heading = _first_child_text(div, "tei:head")
        if heading and METHOD_HEADING.search(heading):
            matched.append(div)
            
    filtered_matches = [
        div
        for div in matched
        if not any(ancestor in matched for ancestor in div.iterancestors())
    ]
    
    return filtered_matches if filtered_matches else top_level


def _first_child_text(root: etree._Element, path: str) -> str:
    nodes = root.xpath(path, namespaces=TEI_NS)
    return _node_text(nodes[0]) if nodes else ""


def _node_text(node: etree._Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _joined_paragraphs(containers: list[etree._Element]) -> str:
    paragraphs: list[str] = []
    for container in containers:
        for paragraph in container.xpath(".//tei:p", namespaces=TEI_NS):
            rendered = copy.deepcopy(paragraph)
            for ref in rendered.xpath(".//tei:ref[@type='bibr']", namespaces=TEI_NS):
                target = (ref.get("target") or "").lstrip("#")
                if target:
                    ref.text = f"[{target}]"
            text = " ".join("".join(rendered.itertext()).split())
            if text and not BIBLIOGRAPHY_PARAGRAPH.match(text):
                paragraphs.append(text)
    return "\n".join(paragraphs)
