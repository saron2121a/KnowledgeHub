import pytest
from backend import cache


@pytest.fixture(autouse=True)
def isolated_version_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "_VERSION_FILE", tmp_path / "corpus_version.txt")
