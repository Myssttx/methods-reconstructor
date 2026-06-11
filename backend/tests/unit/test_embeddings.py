from app.llm.embeddings import _embedding_batches, _vertex_embedding_location


def test_vertex_embedding_batches_respect_item_limit():
    batches = _embedding_batches(["sentence"] * 501)

    assert [len(batch) for batch in batches] == [250, 250, 1]


def test_vertex_embedding_batches_respect_character_budget():
    batches = _embedding_batches(["x" * 40_000, "y" * 30_000, "z"])

    assert batches == [["x" * 40_000], ["y" * 30_000, "z"]]


def test_vertex_embeddings_use_regional_fallback_for_global_gemini():
    assert _vertex_embedding_location("global", "us-central1") == "us-central1"
    assert _vertex_embedding_location("europe-west4", "us-central1") == "europe-west4"
