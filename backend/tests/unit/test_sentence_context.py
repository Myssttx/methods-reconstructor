import pytest

from app.search import papers_dao


@pytest.mark.asyncio
async def test_sentence_context_uses_one_dense_contiguous_anchor_cluster(monkeypatch):
    async def fake_get_paper(_paper_id):
        return {
            "methods_sentences": [
                {"sentence_id": i, "text": f"sentence {i}"}
                for i in range(30)
            ]
        }

    monkeypatch.setattr(papers_dao, "get_paper", fake_get_paper)

    sentence_ids, passage = await papers_dao.sentence_context_windows(
        "paper",
        [2, 3, 20, 21, 22],
        radius=1,
    )

    assert sentence_ids == [19, 20, 21, 22, 23]
    assert "[2] sentence 2" not in passage
    assert "[20] sentence 20" in passage
