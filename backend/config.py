import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = str(BASE_DIR / "chroma_db")
FRONTEND_DIR = BASE_DIR / "frontend"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))  # seconds

# Local LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
MODEL = os.getenv("MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", 180))

USE_HYBRID = os.getenv("USE_HYBRID", "false").lower() == "true"
USE_RERANK = os.getenv("USE_RERANK", "false").lower() == "true"

CANDIDATES = 15      # passages fetched before reranking
TOP_K = 3            # passages sent to the LLM
MAX_UPLOAD_BYTES = 1_000_000
