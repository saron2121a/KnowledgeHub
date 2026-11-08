
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, ingestion, rag

app = FastAPI(title="KnowledgeHub")


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[dict] = Field(default_factory=list)
    document: str | None = None


def validate_document(document: str | None):
    """Validate a selected document and confirm it exists."""
    if document is None:
        return None

    try:
        name = ingestion.safe_name(document)
    except ValueError as e:
        raise HTTPException(400, str(e))

    available = ingestion.list_documents()
    names = {
        item["name"] if isinstance(item, dict) else item
        for item in available
    }

    if name not in names:
        raise HTTPException(404, "Selected document was not found")

    return name


@app.get("/api/documents")
def documents():
    return ingestion.list_documents()


@app.post("/api/documents")
def upload(file: UploadFile = File(...)):
    try:
        name = ingestion.safe_name(file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))

    raw = file.file.read(config.MAX_UPLOAD_BYTES + 1)

    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 1 MB)")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 text")

    try:
        chunks = ingestion.index_document(name, text)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"name": name, "chunks": chunks, "status": "indexed"}


@app.delete("/api/documents/{name}")
def remove(name: str):
    try:
        ingestion.delete_document(name)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"deleted": name}


@app.post("/api/ask")
def ask(body: AskBody):
    document = validate_document(body.document)

    return rag.ask(
        body.question.strip(),
        body.history,
        document,
    )


@app.get("/api/compare")
def compare(q: str, document: str | None = None):
    selected = validate_document(document)
    return rag.compare(q, selected)


app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
