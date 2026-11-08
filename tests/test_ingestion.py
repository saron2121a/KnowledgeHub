from backend import cache, config, ingestion, retrieval


class FakeCol:
    def __init__(self): self.rows = {}
    def upsert(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas): self.rows[i] = (d, m)
    def _sel(self, where):
        return [i for i, (d, m) in self.rows.items() if not where or m["source"] == where["source"]]
    def get(self, where=None):
        ids = self._sel(where)
        return {"ids": ids, "documents": [self.rows[i][0] for i in ids], "metadatas": [self.rows[i][1] for i in ids]}
    def delete(self, ids=None, where=None):
        for i in (ids if ids is not None else self._sel(where)): self.rows.pop(i, None)


def setup(monkeypatch, tmp_path):
    col = FakeCol()
    monkeypatch.setattr(retrieval, "get_collection", lambda: col)
    monkeypatch.setattr(config, "DOCS_DIR", tmp_path / "docs")
    return col


def test_replacing_a_document_removes_stale_chunks_and_bumps_version(monkeypatch, tmp_path):
    col = setup(monkeypatch, tmp_path)
    ingestion.index_document("a.txt", "\n\n".join(["x " * 300] * 4))
    many = len(col.rows)
    v = cache.corpus_version()
    ingestion.index_document("a.txt", "short text")
    assert many > 1 and len(col.rows) == 1
    assert cache.corpus_version() == v + 1


def test_delete_removes_chunks_file_and_bumps_version(monkeypatch, tmp_path):
    col = setup(monkeypatch, tmp_path)
    ingestion.index_document("a.txt", "hello world")
    v = cache.corpus_version()
    ingestion.delete_document("a.txt")
    assert col.rows == {} and not (config.DOCS_DIR / "a.txt").exists()
    assert cache.corpus_version() == v + 1


def test_empty_document_is_rejected_and_keeps_old_content(monkeypatch, tmp_path):
    col = setup(monkeypatch, tmp_path)
    ingestion.index_document("a.txt", "hello world")
    try:
        ingestion.index_document("a.txt", "   ")
        assert False
    except ValueError:
        pass
    assert len(col.rows) == 1


def test_reindex_all_removes_records_for_missing_files(monkeypatch, tmp_path):
    col = setup(monkeypatch, tmp_path)
    ingestion.index_document("gone.txt", "old text")
    ingestion.index_document("kept.txt", "kept text")
    (config.DOCS_DIR / "gone.txt").unlink()
    ingestion.reindex_all()
    assert {m["source"] for _, m in col.rows.values()} == {"kept.txt"}