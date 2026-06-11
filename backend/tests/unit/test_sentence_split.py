from app.ingest.pipeline import split_sentences


def test_sentence_split_keeps_street_abbreviation_with_sentence():
    sentences = split_sentences(
        "Cells were obtained from Sigma, St. Louis, MO. Samples were washed twice."
    )

    assert sentences == [
        "Cells were obtained from Sigma, St. Louis, MO.",
        "Samples were washed twice.",
    ]
