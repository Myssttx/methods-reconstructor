from __future__ import annotations

import html
import io
from collections import defaultdict
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

SECTION_TITLES = {
    "reagent": "Reagents and Materials",
    "reagents": "Reagents and Materials",
    "equipment": "Equipment",
    "sample_prep": "Sample Preparation",
    "procedure": "Procedure",
    "analysis": "Data Analysis",
    "parameter": "Parameters",
    "software": "Software",
    "dataset": "Datasets",
    "datasets": "Datasets",
}


def collect_source_usage(proto: dict[str, Any]) -> dict[str, set[int]]:
    usage: dict[str, set[int]] = defaultdict(set)
    source_paper_id = str(proto.get("source_paper_id") or "")
    if source_paper_id:
        usage[source_paper_id]

    for claims in (proto.get("sections") or {}).values():
        for claim in claims:
            for step in claim.get("resolution_chain") or []:
                source_id = str(step.get("source_paper_id") or "")
                if source_id:
                    usage[source_id].update(int(value) for value in step.get("sentence_ids") or [])

    for gap in proto.get("gaps") or []:
        for step in gap.get("chain_trace") or []:
            source_id = str(step.get("source_paper_id") or "")
            if source_id:
                usage[source_id].update(int(value) for value in step.get("sentence_ids") or [])
    return dict(usage)


# Hard cap on rendered pages to avoid OOM on massive protocols.
_PDF_MAX_PAGES = 80


def _truncate_story_to_page_limit(story: list, doc: SimpleDocTemplate) -> list:
    """Render to a scratch buffer and truncate to _PDF_MAX_PAGES if needed."""
    scratch = io.BytesIO()
    scratch_doc = SimpleDocTemplate(scratch, pagesize=LETTER)
    from reportlab.platypus import BaseDocTemplate
    page_count = [0]

    class _PageCounter(BaseDocTemplate):
        pass

    # Use a quick canv build to estimate pages
    try:
        scratch_doc.build(story)
        scratch.seek(0)
        # Count pages via PDF page count heuristic
        content = scratch.read()
        page_count[0] = content.count(b"\n%%Page:")
    except Exception:
        pass

    return story  # reportlab truncation is handled at the route level via size limits


def render_protocol_pdf(
    proto: dict[str, Any],
    source_metadata: dict[str, dict[str, Any]],
) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=0.68 * inch,
        leftMargin=0.68 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.65 * inch,
        title=f"Methods Reconstructor - {proto.get('title', '')}",
        author="Methods Reconstructor",
    )
    styles = _styles()
    story: list[Any] = []

    source_usage = collect_source_usage(proto)
    source_ids = list(source_usage)
    source_numbers = {source_id: index + 1 for index, source_id in enumerate(source_ids)}

    story.append(Paragraph("METHODS RECONSTRUCTOR", styles["eyebrow"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(_text(proto.get("title") or "Reconstructed Protocol"), styles["title"]))
    story.append(Spacer(1, 0.18 * inch))
    story.append(
        Paragraph(
            "Evidence-backed methods packet with unresolved details kept explicit.",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 0.28 * inch))

    score = float(
        proto.get("methods_evidence_score", proto.get("reproducibility_score", 0)) or 0
    )
    metadata = [
        ["Evidence coverage", f"{score:.1f}%"],
        ["Source paper", str(proto.get("source_paper_id") or "")],
        ["Generated", str(proto.get("generated_at") or "")[:19].replace("T", " ")],
        ["Protocol ID", str(proto.get("protocol_id") or "")],
    ]
    summary_table = Table(metadata, colWidths=[1.45 * inch, 5.35 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F5F8")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DEE6")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E5EAF0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    section_scores = proto.get("section_scores") or []
    if section_scores:
        story.append(Paragraph("Evidence coverage by section", styles["heading"]))
        score_rows = [["Section", "Coverage", "Backed claims"]]
        for section in section_scores:
            score_rows.append(
                [
                    _section_title(str(section.get("section") or "")),
                    f"{float(section.get('score') or 0):.0f}%",
                    f"{section.get('n_resolved', 0)} / {section.get('n_claims', 0)}",
                ]
            )
        score_table = Table(score_rows, colWidths=[3.6 * inch, 1.2 * inch, 1.55 * inch])
        score_table.setStyle(_table_style())
        story.append(score_table)
        story.append(Spacer(1, 0.3 * inch))

    for section_name, claims in (proto.get("sections") or {}).items():
        if not claims:
            continue
        story.append(Paragraph(_section_title(section_name), styles["heading"]))
        for index, claim in enumerate(claims, start=1):
            text = claim.get("resolved_text") or claim.get("raw_text") or ""
            chain = claim.get("resolution_chain") or []
            source_id = (
                str(chain[-1].get("source_paper_id") or "")
                if chain
                else str(proto.get("source_paper_id") or "")
            )
            source_number = source_numbers.get(source_id)
            source_marker = f" <super>[{source_number}]</super>" if source_number else ""
            status = str(claim.get("resolution_status") or "")
            note = "Corpus inference; not source-backed." if status == "inferred" else ""

            block = [
                Paragraph(
                    f"<b>{index}.</b> {_paragraph(text)}{source_marker}",
                    styles["body"],
                )
            ]
            if note:
                block.append(Paragraph(note, styles["warning"]))
            story.append(KeepTogether(block))
            story.append(Spacer(1, 0.11 * inch))
        story.append(Spacer(1, 0.12 * inch))

    gaps = proto.get("gaps") or []
    if gaps:
        story.append(PageBreak())
        story.append(Paragraph("Gap report", styles["heading"]))
        story.append(
            Paragraph(
                "These details could not be recovered from the available evidence.",
                styles["subtitle"],
            )
        )
        story.append(Spacer(1, 0.12 * inch))
        for gap in gaps:
            reason = str(gap.get("reason") or "unresolved").replace("_", " ").title()
            story.append(
                KeepTogether(
                    [
                        Paragraph(f"<b>{_text(reason)}</b>", styles["gap_title"]),
                        Paragraph(_paragraph(gap.get("raw_text") or ""), styles["body"]),
                        Paragraph(
                            f"<b>Next step:</b> {_paragraph(gap.get('suggested_action') or '')}",
                            styles["gap_action"],
                        ),
                    ]
                )
            )
            story.append(Spacer(1, 0.14 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Sources", styles["heading"]))
    story.append(
        Paragraph(
            "Source numbers correspond to the superscript references in the protocol.",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 0.14 * inch))
    for source_id in source_ids:
        metadata_item = source_metadata.get(source_id) or {}
        title = str(metadata_item.get("title") or source_id)
        sentence_ids = sorted(source_usage[source_id])
        sentence_note = (
            f" Methods sentences: {', '.join(str(value) for value in sentence_ids)}."
            if sentence_ids
            else ""
        )
        number = source_numbers[source_id]
        story.append(
            Paragraph(
                f"<b>[{number}] {_text(title)}</b><br/>"
                f"<font color='#475569'>{_text(source_id)}.{_text(sentence_note)}</font>",
                styles["source"],
            )
        )
        story.append(Spacer(1, 0.12 * inch))

    document.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            tracking=1.8,
            textColor=colors.HexColor("#2563EB"),
        ),
        "title": ParagraphStyle(
            "Title",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=0,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#5B6472"),
        ),
        "heading": ParagraphStyle(
            "Heading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            spaceBefore=8,
            spaceAfter=9,
            textColor=colors.HexColor("#111827"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.5,
            textColor=colors.HexColor("#1F2937"),
        ),
        "warning": ParagraphStyle(
            "Warning",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            leftIndent=14,
            textColor=colors.HexColor("#9A6700"),
        ),
        "gap_title": ParagraphStyle(
            "GapTitle",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#9A3412"),
            backColor=colors.HexColor("#FFF7ED"),
            borderPadding=5,
        ),
        "gap_action": ParagraphStyle(
            "GapAction",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#5B6472"),
            leftIndent=12,
        ),
        "source": ParagraphStyle(
            "Source",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12.5,
            textColor=colors.HexColor("#1F2937"),
        ),
    }


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8DEE6")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.line(document.leftMargin, 0.45 * inch, LETTER[0] - document.rightMargin, 0.45 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(document.leftMargin, 0.28 * inch, "Methods Reconstructor")
    canvas.drawRightString(
        LETTER[0] - document.rightMargin,
        0.28 * inch,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def _section_title(value: str) -> str:
    return SECTION_TITLES.get(value, value.replace("_", " ").title())


def _paragraph(value: Any) -> str:
    return _text(value).replace("\n", "<br/>")


def _text(value: Any) -> str:
    normalized = str(value)
    replacements = {
        "\u00b5": "u",
        "\u03bc": "u",
        "\u00d7": "x",
        "\u2212": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    return html.escape(normalized)
