
from backend import ingestion, retrieval


def d(id_):
    return {
        "id": id_,
        "source": "x.txt",
        "chunk": 0,
        "text": id_,
    }


def test_rrf_rewards_items_found_by_both_lists():
    fused = retrieval.rrf([
        [d("a"), d("b"), d("c")],
        [d("c"), d("a"), d("z")],
    ])

    assert [x["id"] for x in fused][:2] == ["a", "c"]


def test_chunking_respects_size():
    text = "\n\n".join(["word " * 100] * 5)

    assert all(
        len(chunk) <= 800
        for chunk in ingestion.chunk_text(text)
    )


def test_filename_validation():
    assert ingestion.safe_name("notes.txt") == "notes.txt"

    for bad in ["a.pdf", "../x.txt", "sub/x.txt", "..\\x.txt", ""]:
        try:
            ingestion.safe_name(bad)
            assert False, bad
        except ValueError:
            pass


def test_vector_search_respects_selected_document(monkeypatch):
    class FakeCollection:
        def get(self, where=None, include=None):
            if where == {"source": "a.txt"}:
                return {"ids": ["a1"]}

            return {"ids": ["a1", "b1", "c1", "d1", "e1"]}

        def query(self, **kwargs):
            assert kwargs["where"] == {"source": "a.txt"}
            assert kwargs["n_results"] == 1

            return {
                "ids": [["a1"]],
                "documents": [["Content from document A"]],
                "metadatas": [[{"source": "a.txt", "chunk": 0}]],
            }

    monkeypatch.setattr(
        retrieval,
        "get_collection",
        lambda: FakeCollection(),
    )

    results = retrieval.vector_search("question", 3, "a.txt")

    assert len(results) == 1
    assert results[0]["source"] == "a.txt"


def test_vector_search_returns_empty_for_document_without_chunks(monkeypatch):
    class FakeCollection:
        def get(self, where=None, include=None):
            if where == {"source": "empty.txt"}:
                return {"ids": []}

            return {"ids": ["a1", "b1", "c1", "d1", "e1"]}

        def query(self, **kwargs):
            raise AssertionError(
                "Query should not run for an empty scope"
            )

    monkeypatch.setattr(
        retrieval,
        "get_collection",
        lambda: FakeCollection(),
    )

    results = retrieval.vector_search("question", 3, "empty.txt")

    assert results == []


def test_bm25_search_respects_selected_document(monkeypatch):
    class FakeCollection:
        def get(self, where=None, include=None):
            if where == {"source": "a.txt"}:
                return {
                    "ids": ["a1"],
                    "documents": [
                        "Redis caching improves application performance"
                    ],
                    "metadatas": [
                        {"source": "a.txt", "chunk": 0}
                    ],
                }

            return {
                "ids": ["a1", "b1"],
                "documents": [
                    "Redis caching improves application performance",
                    "Python programming uses variables and functions",
                ],
                "metadatas": [
                    {"source": "a.txt", "chunk": 0},
                    {"source": "b.txt", "chunk": 0},
                ],
            }

    monkeypatch.setattr(
        retrieval,
        "get_collection",
        lambda: FakeCollection(),
    )

    retrieval.invalidate_bm25()

    results = retrieval.keyword_search("Redis caching", 3, "a.txt")

    assert results
    assert all(item["source"] == "a.txt" for item in results)

    retrieval.invalidate_bm25()
