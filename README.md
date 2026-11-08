# KnowledgeHub – Intelligent Document Assistant

Web RAG app: upload .txt documents, ask questions, get answers with source references.
Pipeline: **Redis check → (miss) hybrid search (vector + BM25 + RRF) → cross-encoder rerank → Claude → cache answer**.

## Setup
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # then put your ANTHROPIC_API_KEY in .env
docker compose up -d                                    # Redis (maxmemory 100mb, allkeys-lru)
python -m backend.ingestion                             # indexes docs/*.txt
uvicorn backend.main:app --reload                       # open http://localhost:8000
pytest                                                  # cache + retrieval tests (no Redis/API needed)
```

## Demo script
1. Ask "What is a TTL?" → badge **MISS**, shows retrieval / rerank / generation timings.
2. Ask it again → badge **HIT**, served from Redis, much faster, same sources.
3. Upload or delete a document → ask again → **MISS** (corpus version bumped).
4. Ask something unrelated → "I don't have enough information" (not cached).
5. `docker compose stop redis` → ask → **BYPASS** (app still answers).
6. With hybrid/rerank enabled, type a question and press **Compare retrieval** to see vector vs hybrid vs reranked picks (disabled methods show `null`).

## Config (.env)
`USE_HYBRID`, `USE_RERANK` (both default to `false`: get the core app and cache working first, then set each to `true` one at a time and re-run the demo), `CACHE_TTL`, `MODEL`.

## Design notes
- Cache-aside; key = hash(normalized question) + corpus version + retrieval mode.
- Only successful, standalone answers are cached; follow-ups bypass the cache.
- The corpus version is kept in `data/corpus_version.txt`, not Redis, so invalidation still works if Redis is down during an update.
- Redis errors never break the app; corrupt cache entries are treated as misses. Eviction: `allkeys-lru` (see caching-summary.md).
