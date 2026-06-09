from app.evaluation.variability import label_agreement, signature_jaccard, variability_report

RUN_A = [
    {
        "raw_text": "Cells were washed twice.",
        "type": "procedure",
        "specificity": "fully_described",
        "resolution_status": "resolved",
    }
]
RUN_B = [dict(RUN_A[0])]
RUN_C = [
    {
        **RUN_A[0],
        "specificity": "partially_described",
    },
    {
        "raw_text": "Samples were frozen.",
        "type": "sample_prep",
        "specificity": "fully_described",
        "resolution_status": "resolved",
    },
]


def test_identical_runs_have_full_agreement():
    assert signature_jaccard(RUN_A, RUN_B) == 1.0
    assert label_agreement(RUN_A, RUN_B) == 1.0


def test_report_exposes_count_and_label_variability():
    report = variability_report([RUN_A, RUN_B, RUN_C])

    assert report["claim_counts"] == [1, 1, 2]
    assert report["claim_count_cv"] > 0
    assert report["pairwise_signature_jaccard_min"] < 1
    assert report["pairwise_label_agreement_min"] == 0
