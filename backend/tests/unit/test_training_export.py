from app.evaluation.training_export import examples_from_protocol, source_backed


def test_source_backed_rejects_inferred_and_evidence_free_resolution():
    assert not source_backed({"resolution_status": "inferred"})
    assert not source_backed(
        {
            "resolution_status": "resolved",
            "specificity": "shortcut_citation",
            "resolution_chain": [{"source_paper_id": "paper", "sentence_ids": []}],
        }
    )


def test_export_keeps_direct_and_sentence_backed_claims():
    protocol = {
        "protocol_id": "p1",
        "source_paper_id": "source",
        "sections": {
            "procedure": [
                {
                    "paper_id": "source",
                    "raw_sentence_id": 1,
                    "raw_text": "Wash twice.",
                    "resolved_text": "Wash twice.",
                    "type": "procedure",
                    "specificity": "fully_described",
                    "resolution_status": "resolved",
                    "resolution_chain": [],
                },
                {
                    "paper_id": "source",
                    "raw_sentence_id": 2,
                    "raw_text": "As described previously.",
                    "resolved_text": "Incubate for ten minutes.",
                    "type": "procedure",
                    "specificity": "shortcut_citation",
                    "resolution_status": "resolved",
                    "resolution_chain": [
                        {
                            "source_paper_id": "cited",
                            "sentence_ids": [4],
                            "extracted_text": "Incubate for ten minutes.",
                        }
                    ],
                },
            ]
        },
    }

    examples = list(examples_from_protocol(protocol))

    assert len(examples) == 2
    assert examples[1]["evidence"][0]["sentence_ids"] == [4]
