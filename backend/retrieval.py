
"""Vector search (ChromaDB), keyword search (BM25) and Reciprocal Rank Fusion."""
import re

_collection = None
_bm25_cache = {}


def get_collection():
    global _collection

    if _collection is None:
        import chromadb
        from . import config

        _collection = chromadb.PersistentClient(
            path=config.CHROMA_DIR
        ).get_or_create_collection("docs")

    return _collection


def invalidate_bm25():
    """Clear every cached BM25 index after the document collection changes."""
    _bm25_cache.clear()


def tokenize(text: str):
    return re.findall(r"\w+", text.lower())


def _item(id_, text, meta):
    return {
        "id": id_,
        "source": meta["source"],
        "chunk": meta["chunk"],
        "text": text,
    }


def _where(source: str | None):
    """Build a ChromaDB metadata filter for a selected document."""
    return {"source": source} if source else None


def vector_search(query: str, k: int, source: str | None = None):
    """Search all documents or restrict vector search to one document."""
    col = get_collection()
    where = _where(source)

    # ChromaDB 1.5.9 does not support where= in Collection.count().
    # Get the IDs matching the selected document to determine its count.
    if where:
        count = len(col.get(where=where, include=[])["ids"])
    else:
        count = col.count()

    if count == 0:
        return []

    kwargs = {
        "query_texts": [query],
        "n_results": min(k, count),
    }

    if where:
        kwargs["where"] = where

    res = col.query(**kwargs)

    return [
        _item(i, d, m)
        for i, d, m in zip(
            res["ids"][0],
            res["documents"][0],
            res["metadatas"][0],
        )
    ]


def _build_bm25(source: str | None = None):
    """Build and cache a BM25 index for all documents or one selected document."""
    from rank_bm25 import BM25Okapi

    col = get_collection()
    where = _where(source)

    data = col.get(where=where) if where else col.get()

    items = [
        _item(i, d, m)
        for i, d, m in zip(
            data["ids"],
            data["documents"],
            data["metadatas"],
        )
    ]

    model = (
        BM25Okapi([tokenize(item["text"]) for item in items])
        if items
        else None
    )

    _bm25_cache[source or "all"] = (model, items)
    return model, items


def keyword_search(query: str, k: int, source: str | None = None):
    """Search using BM25, restricted to the selected document when specified."""
    scope = source or "all"

    if scope not in _bm25_cache:
        _build_bm25(source)

    model, items = _bm25_cache[scope]

    if model is None:
        return []

    query_tokens = set(tokenize(query))

    if not query_tokens:
        return []

    scores = model.get_scores(tokenize(query))

    ranked = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:k]

    # BM25 scores can be negative for valid matches in small collections.
    # Check actual term overlap instead of requiring a positive score.
    return [
        items[i]
        for i in ranked
        if query_tokens.intersection(tokenize(items[i]["text"]))
    ]


def rrf(result_lists, k: int = 60):
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)) across ranked lists."""
    scores, items = {}, {}

    for results in result_lists:
        for rank, item in enumerate(results, start=1):
            scores[item["id"]] = (
                scores.get(item["id"], 0.0) + 1.0 / (k + rank)
            )
            items[item["id"]] = item

    return [
        items[i]
        for i in sorted(scores, key=scores.get, reverse=True)
    ]


def hybrid_search(query: str, n: int, source: str | None = None):
    """Combine vector and keyword results using Reciprocal Rank Fusion."""
    fused = rrf([
        vector_search(query, n, source),
        keyword_search(query, n, source),
    ])

    return fused[:n]
