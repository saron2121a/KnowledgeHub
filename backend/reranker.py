"""Cross-encoder reranking. Falls back to the original order if the model can't load."""
import logging
from . import config

log = logging.getLogger("reranker")
_model = None
_failed = False


def _load():
    global _model, _failed
    if _model is None and not _failed:
        try:
            from sentence_transformers import CrossEncoder
            _model = CrossEncoder(config.RERANK_MODEL)
        except Exception as e:  # missing package, no internet, unsupported Python...
            log.warning("Reranker unavailable, skipping rerank: %s", e)
            _failed = True
    return _model


def rerank(query: str, candidates: list, top_n: int):
    """Returns (passages, status). status is 'reranked' or 'unavailable' (fallback to original order)."""
    model = _load()
    if model is None:
        return candidates[:top_n], "unavailable"
    if not candidates:
        return [], "reranked"
    scores = model.predict([(query, c["text"]) for c in candidates])
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)[:top_n]
    return [{**c, "score": float(s)} for c, s in ranked], "reranked"