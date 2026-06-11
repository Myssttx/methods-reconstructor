from app.exporting.pdf_export import collect_source_usage, render_protocol_pdf

PROTO = {
    "protocol_id": "protocol-1",
    "job_id": "job-1",
    "source_paper_id": "doi:10.1000/source",
    "title": "Test protocol",
    "methods_evidence_score": 75.0,
    "generated_at": "2026-06-09T00:00:00+00:00",
    "section_scores": [
        {"section": "procedure", "score": 75.0, "n_claims": 4, "n_resolved": 3}
    ],
    "sections": {
        "procedure": [
            {
                "raw_text": "Cells were washed.",
                "resolved_text": "Cells were washed twice with PBS.",
                "resolution_status": "resolved",
                "resolution_chain": [
                    {
                        "source_paper_id": "doi:10.1000/cited",
                        "sentence_ids": [4, 5],
                    }
                ],
            }
        ]
    },
    "gaps": [
        {
            "reason": "source_unavailable",
            "raw_text": "Incubation followed prior work.",
            "suggested_action": "Locate the cited full text.",
            "chain_trace": [],
        }
    ],
}


def test_collect_source_usage_includes_original_and_chain_sources():
    usage = collect_source_usage(PROTO)

    assert usage["doi:10.1000/source"] == set()
    assert usage["doi:10.1000/cited"] == {4, 5}


def test_render_protocol_pdf_produces_pdf_document():
    content = render_protocol_pdf(
        PROTO,
        {
            "doi:10.1000/source": {"title": "Original paper"},
            "doi:10.1000/cited": {"title": "Cited methods paper"},
        },
    )

    assert content.startswith(b"%PDF")
    assert len(content) > 2000
