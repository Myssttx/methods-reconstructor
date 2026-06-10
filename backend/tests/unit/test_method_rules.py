from app.agent.method_rules import classify_specificity, classify_type


def test_classify_specificity_preserves_reference_ids():
    specificity, references = classify_specificity(
        "Dissociation was performed as described previously [R9][b12][ref_4]."
    )

    assert specificity == "shortcut_citation"
    assert references == ["R9", "b12", "ref_4"]


def test_centrifuged_sentence_is_a_procedure_not_equipment():
    assert classify_type("Samples were centrifuged at 300g for 5 minutes.") == "procedure"


def test_concentration_unit_is_a_reagent_without_matching_arbitrary_mm_text():
    assert classify_type("A 10 mM Tris solution was prepared.") == "reagent"
    assert classify_type("Summary statistics were reported.") == "procedure"
