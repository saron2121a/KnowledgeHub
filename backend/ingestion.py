
"""Document processing: chunk -> embed (Chroma does this) -> store."""
import os
import re

from . import cache, config, retrieval

SAFE_NAME = re.compile(r"^[\w\-. ]{1,100}\.txt$")


def safe_name(name: str) -> str:
    """Reject filenames containing paths or unsafe characters."""
    name = name or ""

    if (
        "/" in name
        or "\\" in name
        or ".." in name
        or not SAFE_NAME.fullmatch(name)
    ):
        raise ValueError(
            "Only .txt files with simple names (no folders) are allowed"
        )

    return name


def chunk_text(text: str, size: int = 800, overlap: int = 100):
    """Split text into overlapping chunks."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Invalid chunk size or overlap")

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        while len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""

            chunks.append(paragraph[:size])
            paragraph = paragraph[size - overlap:]

        if len(current) + len(paragraph) + 2 <= size:
            current = (
                f"{current}\n\n{paragraph}" if current else paragraph
            )
        else:
            if current:
                chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def _delete_chunks(name: str):
    """Delete all ChromaDB chunks belonging to one document."""
    retrieval.get_collection().delete(where={"source": name})


def index_document(name: str, text: str, bump: bool = True) -> int:
    """
    Index or reindex one document.

    New chunks are written before stale chunks are removed,
    so a failed update does not immediately empty the document.
    """
    name = safe_name(name)
    chunks = chunk_text(text)

    if not chunks:
        raise ValueError("Document is empty")

    collection = retrieval.get_collection()

    new_ids = [
        f"{name}:{i}"
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=new_ids,
        documents=chunks,
        metadatas=[
            {"source": name, "chunk": i}
            for i in range(len(chunks))
        ],
    )

    keep = set(new_ids)

    existing = collection.get(
        where={"source": name}
    )["ids"]

    stale = [
        chunk_id
        for chunk_id in existing
        if chunk_id not in keep
    ]

    if stale:
        collection.delete(ids=stale)

    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = config.DOCS_DIR / (name + ".tmp")
    destination = config.DOCS_DIR / name

    try:
        temporary_file.write_text(text, encoding="utf-8")
        os.replace(temporary_file, destination)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()

    retrieval.invalidate_bm25()

    if bump:
        cache.bump_version()

    return len(chunks)


def delete_document(name: str):
    """Delete a document from ChromaDB and the docs directory."""
    name = safe_name(name)

    _delete_chunks(name)

    (config.DOCS_DIR / name).unlink(missing_ok=True)

    retrieval.invalidate_bm25()
    cache.bump_version()


def list_documents():
    """Return indexed documents and their chunk counts."""
    data = retrieval.get_collection().get()

    counts = {}

    for metadata in data["metadatas"]:
        source = metadata["source"]
        counts[source] = counts.get(source, 0) + 1

    return [
        {
            "name": name,
            "chunks": count,
            "status": "indexed",
        }
        for name, count in sorted(counts.items())
    ]


def reindex_all():
    """Reindex documents on disk and remove stale ChromaDB records."""
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(config.DOCS_DIR.glob("*.txt"))
    on_disk = {path.name for path in files}

    removed = False

    # Remove indexed documents that no longer exist on disk.
    for document in list_documents():
        if document["name"] not in on_disk:
            _delete_chunks(document["name"])
            print(
                f"Removed {document['name']} "
                "(file no longer in docs/)"
            )
            removed = True

    if removed:
        retrieval.invalidate_bm25()

    # Reindex every document currently on disk.
    for path in files:
        chunks = index_document(
            path.name,
            path.read_text(encoding="utf-8"),
            bump=False,
        )

        print(f"Indexed {path.name}: {chunks} chunks")

    # Invalidate cached answers after the reindex operation.
    cache.bump_version()


if __name__ == "__main__":
    reindex_all()
