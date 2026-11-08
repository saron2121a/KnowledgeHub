import redis
from backend import cache, rag


class FakeRedis:
    def __init__(self): self.d = {}
    def get(self, k): return self.d.get(k)
    def setex(self, k, ttl, v): self.d[k] = v
    def delete(self, k): self.d.pop(k, None)


class DownRedis:
    def __getattr__(self, name):
        def fail(*a, **k): raise redis.RedisError("down")
        return fail


def setup(monkeypatch, backend):
    monkeypatch.setattr(cache, "client", lambda: backend)
    calls = {"gen": 0, "ret": 0}
    passage = {"id": "a:0", "source": "a.txt", "chunk": 0, "text": "Redis is a cache."}

    def fake_retrieve(q, source=None):
        calls["ret"] += 1
        return [passage], [passage], {"retrieval_ms": 1, "rerank_ms": 1}, "disabled"

    def fake_generate(q, passages, history):
        calls["gen"] += 1
        return "Redis is a cache [1]."

    monkeypatch.setattr(rag, "retrieve_context", fake_retrieve)
    monkeypatch.setattr(rag, "generate", fake_generate)
    return calls


def test_miss_then_hit_skips_retrieval_and_generation(monkeypatch):
    calls = setup(monkeypatch, FakeRedis())
    first = rag.ask("What is Redis?")
    second = rag.ask("  what is   REDIS? ")           # normalized to the same key
    assert first["cache"] == "MISS" and second["cache"] == "HIT"
    assert calls == {"gen": 1, "ret": 1}
    assert second["sources"] == first["sources"]


def test_version_bump_invalidates(monkeypatch):
    calls = setup(monkeypatch, FakeRedis())
    rag.ask("What is Redis?")
    cache.bump_version()
    assert rag.ask("What is Redis?")["cache"] == "MISS"
    assert calls["gen"] == 2


def test_redis_down_bypasses_cache(monkeypatch):
    calls = setup(monkeypatch, DownRedis())
    out = rag.ask("What is Redis?")
    assert out["cache"] == "BYPASS" and out["answer"] and calls["gen"] == 1


def test_follow_up_skips_cache(monkeypatch):
    calls = setup(monkeypatch, FakeRedis())
    hist = [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
    assert rag.ask("and then?", hist)["cache"] == "BYPASS"


def test_version_bump_works_while_redis_is_down(monkeypatch):
    monkeypatch.setattr(cache, "client", lambda: DownRedis())
    before = cache.corpus_version()
    cache.bump_version()                       # must not depend on Redis
    assert cache.corpus_version() == before + 1


def test_malformed_cache_entry_is_a_miss(monkeypatch):
    fake = FakeRedis()
    calls = setup(monkeypatch, fake)
    fake.d[cache.make_key("What is Redis?", rag.mode())] = "{not json"
    assert rag.ask("What is Redis?")["cache"] == "MISS"
    assert calls["gen"] == 1