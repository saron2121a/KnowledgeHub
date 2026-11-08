from backend import reranker


def test_fallback_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(reranker, "_load", lambda: None)
    cands = [{"id": str(i), "source": "a.txt", "chunk": i, "text": "t"} for i in range(5)]
    picked, status = reranker.rerank("q", cands, 3)
    assert status == "unavailable" and picked == cands[:3]


def test_scores_are_used_when_model_loads(monkeypatch):
    class Fake:
        def predict(self, pairs): return [0.1, 0.9, 0.5]
    monkeypatch.setattr(reranker, "_load", lambda: Fake())
    cands = [{"id": str(i), "source": "a.txt", "chunk": i, "text": "t"} for i in range(3)]
    picked, status = reranker.rerank("q", cands, 2)
    assert status == "reranked" and [p["chunk"] for p in picked] == [1, 2]