
"""RAG pipeline with Redis cache-aside and local Ollama generation."""
import json
import time
import urllib.error
import urllib.request

from . import cache, config, reranker, retrieval

INSUFFICIENT = "I don't have enough information"


def mode() -> str:
    """Include retrieval settings and model identity in the cache key."""
    return (
        f"h{int(config.USE_HYBRID)}"
        f"r{int(config.USE_RERANK)}"
        f":{config.LLM_PROVIDER}:{config.MODEL}"
    )


def normalize_question(question: str) -> str:
    """Normalize a question for comparison."""
    return " ".join(question.lower().split())


def is_repeat_question(question: str, history: list) -> bool:
    """Check whether the current question exactly repeats an earlier user question."""
    current = normalize_question(question)

    for item in history:
        if item.get("role") == "user":
            previous = item.get("content")

            if isinstance(previous, str):
                if normalize_question(previous) == current:
                    return True

    return False


def followup_query(question: str, history: list) -> str:
    """Build a retrieval query from the last two user turns and the new question."""
    prior = [
        h["content"]
        for h in history
        if h.get("role") == "user"
        and isinstance(h.get("content"), str)
    ]

    return " ".join(prior[-2:] + [question])


def retrieve_context(query: str, source: str | None = None):
    """Search -> optional rerank -> top passages, optionally within one document."""
    t = time.perf_counter()

    if config.USE_HYBRID:
        cands = retrieval.hybrid_search(
            query, config.CANDIDATES, source
        )
    else:
        count = config.CANDIDATES if config.USE_RERANK else config.TOP_K
        cands = retrieval.vector_search(query, count, source)

    t_ret = (time.perf_counter() - t) * 1000

    t = time.perf_counter()

    if config.USE_RERANK:
        top, rerank_status = reranker.rerank(
            query, cands, config.TOP_K
        )
    else:
        top, rerank_status = cands[:config.TOP_K], "disabled"

    t_rr = (time.perf_counter() - t) * 1000

    return (
        cands,
        top,
        {
            "retrieval_ms": round(t_ret),
            "rerank_ms": round(t_rr),
        },
        rerank_status,
    )


def generate(question: str, passages: list, history: list) -> str:
    """Generate an answer using the local Ollama chat API."""
    if config.LLM_PROVIDER != "ollama":
        raise RuntimeError(
            f"Unsupported LLM provider: {config.LLM_PROVIDER}"
        )

    context = "\n\n".join(
        f"[{i + 1}] ({p['source']}, chunk {p['chunk']}) {p['text']}"
        for i, p in enumerate(passages)
    )

    system_prompt = (
        "You are the question-answering assistant for KnowledgeHub. "
        "Answer using ONLY the supplied numbered document context. "
        "Do not use outside knowledge or invent facts. "
        "Cite supporting passages using their numbers, like [1]. "
        f"If the context does not contain enough information to answer, "
        f"reply starting exactly with: {INSUFFICIENT}"
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    for item in history[-6:]:
        role = item.get("role")
        content = item.get("content")

        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({
                "role": role,
                "content": content,
            })

    # Ensure the first conversation message after the system message is a user message.
    while len(messages) > 1 and messages[1]["role"] != "user":
        messages.pop(1)

    messages.append({
        "role": "user",
        "content": (
            f"Document context:\n{context}\n\n"
            f"Question: {question}"
        ),
    })

    payload = {
        "model": config.MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 600,
        },
    }

    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=config.OLLAMA_TIMEOUT
        ) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Check that Ollama is running "
            "and that the local API is available."
        ) from exc

    answer = result.get("message", {}).get("content")

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Ollama returned an empty or invalid answer.")

    return answer.strip()


def _sources(passages):
    return [
        {
            "source": p["source"],
            "chunk": p["chunk"],
            "snippet": p["text"][:200],
        }
        for p in passages
    ]


def ask(
    question: str,
    history: list | None = None,
    document: str | None = None,
) -> dict:
    """Answer from all documents or restrict the answer to one selected document."""
    start = time.perf_counter()
    history = history or []

    scope = document or "all"

    # An exact repeat is a standalone question, not a contextual follow-up.
    repeated = is_repeat_question(question, history)
    follow_up = bool(history) and not repeated

    key, redis_ok = None, True

    # Check Redis before retrieval or generation for standalone questions.
    if not follow_up:
        key, cached, redis_ok = cache.lookup(
            question, mode(), scope
        )

        if cached:
            return {
                **cached,
                "cache": "HIT",
                "from": "redis",
                "scope": scope,
                "retrieved": 0,
                "reranked": 0,
                "rerank_status": "n/a (cache hit)",
                "timings": {},
                "ms": round((time.perf_counter() - start) * 1000),
            }

    # Genuine follow-ups use conversation context during retrieval.
    query = (
        followup_query(question, history)
        if follow_up
        else question
    )

    # Restrict retrieval to the selected document when one is specified.
    cands, top, timings, rerank_status = retrieve_context(
        query, document
    )

    t = time.perf_counter()

    # Do not inject old conversation history into standalone questions.
    generation_history = history if follow_up else []

    answer = (
        generate(question, top, generation_history)
        if top
        else INSUFFICIENT + " (no documents indexed)."
    )

    timings["generation_ms"] = round(
        (time.perf_counter() - t) * 1000
    )

    insufficient = answer.strip().startswith(INSUFFICIENT)

    result = {
        "answer": answer,
        "sources": [] if insufficient else _sources(top),
    }

    # Cache only successful standalone answers.
    if key and redis_ok and top and not insufficient:
        cache.store(key, result)

    status = (
        "BYPASS"
        if (follow_up or not redis_ok)
        else "MISS"
    )

    reason = (
        "follow-up question"
        if follow_up
        else ("redis unavailable" if not redis_ok else "")
    )

    return {
        **result,
        "cache": status,
        "reason": reason,
        "from": "generated",
        "scope": scope,
        "retrieved": len(cands),
        "reranked": (
            len(top) if rerank_status == "reranked" else 0
        ),
        "rerank_status": rerank_status,
        "timings": timings,
        "ms": round((time.perf_counter() - start) * 1000),
    }


def compare(
    question: str,
    document: str | None = None,
) -> dict:
    """Show which passages each enabled retrieval method selects."""
    ref = lambda ps: [
        {"source": p["source"], "chunk": p["chunk"]}
        for p in ps
    ]

    hyb = (
        retrieval.hybrid_search(
            question, config.CANDIDATES, document
        )
        if config.USE_HYBRID
        else None
    )

    out = {
        "vector": ref(
            retrieval.vector_search(
                question, config.TOP_K, document
            )
        ),
        "hybrid": (
            ref(hyb[:config.TOP_K])
            if hyb is not None
            else None
        ),
        "reranked": None,
    }

    if config.USE_RERANK:
        pool = (
            hyb
            if hyb is not None
            else retrieval.vector_search(
                question, config.CANDIDATES, document
            )
        )

        picked, status = reranker.rerank(
            question, pool, config.TOP_K
        )

        out["reranked"] = (
            ref(picked)
            if status == "reranked"
            else "unavailable (model failed to load)"
        )

    return out
