"""Learn-module content and the assistant's lesson retrieval (offline)."""

import asyncio

from app.content.lessons import LESSONS, LESSONS_BY_ID, keyword_rank, lesson_text


def test_lessons_are_well_formed():
    ids = [lesson["id"] for lesson in LESSONS]
    assert len(ids) == len(set(ids)), "duplicate lesson id"
    for lesson in LESSONS:
        assert lesson["title"] and lesson["summary"] and lesson["theme"]
        assert lesson["minutes"] > 0
        assert lesson["sections"] and all(h and b for h, b in lesson["sections"])
        assert lesson["key_terms"]
        assert lesson_text(lesson).startswith(lesson["title"])
    assert set(LESSONS_BY_ID) == set(ids)


def test_keyword_ranking_finds_the_right_lesson():
    assert keyword_rank("what is a P/E ratio?")[0]["id"] == "fundamentals-basics"
    assert keyword_rank("should I spread money across sectors, diversification")[0]["id"] == "diversification"
    assert keyword_rank("how do I open a CDS account with a stockbroker")[0]["id"] == "how-the-cse-works"
    assert keyword_rank("zz qq") == []


def test_lesson_search_falls_back_when_embeddings_fail(monkeypatch):
    from app.services.agent import embeddings, tools

    async def boom(*a, **k):
        raise RuntimeError("embedding service down")

    monkeypatch.setattr(embeddings, "get_embedding", boom)
    monkeypatch.setattr(embeddings, "get_embeddings_batch", boom)
    monkeypatch.setattr(tools, "_lesson_vectors", None)

    found = asyncio.run(tools._relevant_lessons("what does the ASPI index measure"))
    assert found and found[0]["lesson_id"] == "market-indices"
    assert "ASPI" in found[0]["text"]
