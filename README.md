# KnowledgeHub – Intelligent Document Assistant

# Part 1: Application Description

## 1. About the Project

KnowledgeHub is a web application that allows users to upload text documents and ask questions about the information they contain.

Instead of manually searching through documents, users can type a question and receive an answer based on the uploaded content. The application also stores previously generated answers in Redis, allowing it to respond faster when the same question is asked again.

The main goal of the project is to make finding information in documents easier while demonstrating how caching improves application performance.

## 2. Main Features

- Upload, view, replace, and delete text documents.
- Ask questions about uploaded documents.
- Receive answers based on document content.
- View the sources used to generate an answer.
- Search within one selected document or across all uploaded documents.
- Ask follow-up questions during a conversation.
- Reuse previously generated answers to reduce waiting time.
- Continue answering questions when Redis is unavailable.
- Compare vector search and hybrid search performance.

## 3. Technologies Used

| Technology                | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| Python                    | Main programming language                |
| FastAPI                   | Backend API and application framework    |
| HTML, CSS, and JavaScript | Build the web interface                  |
| ChromaDB                  | Store and search document information    |
| Redis / Memurai           | Store previously generated answers       |
| Ollama and Qwen 2.5 3B    | Generate answers locally                 |
| BM25                      | Support keyword-based document searching |
| Sentence Transformers     | Support reranking of retrieved passages  |
| pytest                    | Test the application                     |

## 4. How the Application Works

1. The user uploads a `.txt` document.
2. The application reads the document and divides its content into smaller text chunks.
3. The chunks are converted into vector embeddings and stored in ChromaDB.
4. The user submits a question.
5. The application checks Redis to see whether an answer to that question is already cached.
6. If the answer is cached, it is returned immediately with its source references.
7. If the answer is not cached, the application retrieves relevant document passages, optionally reranks them, and sends the relevant context to the local language model through Ollama.
8. The generated answer and its sources are returned to the user. Successful standalone answers are also stored in Redis for future requests.

## 5. Project Structure

```text
Knowledge Hub/
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── ingestion.py
│   ├── retrieval.py
│   ├── rag.py
│   ├── cache.py
│   └── reranker.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── docs/
│   ├── global_warming_overview.txt
│   ├── sample.txt
│   └── test_second.txt
│
├── tests/
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 6. Installation and Setup

### Requirements

- Python 3.13
- Ollama
- Redis or Memurai
- Git (optional, for cloning the repository)

### Installation Steps

**1. Create and activate a virtual environment.**

Run these commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**2. Install the required Python packages.**

```powershell
python -m pip install -r requirements.txt
```

**3. Create the environment configuration file.**

```powershell
copy .env.example .env
```

The default configuration uses Ollama with the Qwen 2.5 3B model.

**4. Start Redis.**

Choose one of the following options:

- **Using Docker:** Run this command from the project root:

```powershell
docker compose up -d
```

The included Docker Compose configuration starts Redis 7 on port `6379`, with a 100 MB memory limit and the `allkeys-lru` eviction policy.

- **Using Memurai:** Start the Memurai service through Windows Services.

For Memurai, configure the memory limit to 100 MiB and the eviction policy to `allkeys-lru`. These runtime settings may need to be reapplied after restarting the service.

Both options should make Redis available at `localhost:6379`.

**5. Download the language model.**

Make sure Ollama is installed and running, then execute:

```powershell
ollama pull qwen2.5:3b
```

**6. Index the sample documents.**

```powershell
python -m backend.ingestion
```

**7. Start the application.**

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Open the application in your browser:

`http://127.0.0.1:8002`

The API documentation is available at:

`http://127.0.0.1:8002/docs`

### Configuration

The `.env.example` file contains the default application configuration.

Important settings include:

- `LLM_PROVIDER`: Selects the language model provider.
- `MODEL`: Specifies the language model.
- `OLLAMA_BASE_URL`: Ollama server address.
- `REDIS_HOST` and `REDIS_PORT`: Redis connection settings.
- `CACHE_TTL`: Cache expiration time in seconds.
- `USE_HYBRID`: Enables or disables hybrid retrieval.
- `USE_RERANK`: Enables or disables reranking.
- `RERANK_MODEL`: Specifies the reranking model.

The supplied example configuration uses vector retrieval with reranking enabled. Hybrid retrieval is disabled by default.

## 7. Testing

Run the automated tests using:

```powershell
python -m pytest tests -v
```

The tests cover:

- Redis cache hits and misses.
- Cache invalidation after document changes.
- Redis failure handling.
- Follow-up question handling.
- Document ingestion and deletion.
- Document isolation during retrieval.
- Vector and hybrid retrieval.
- Reranking behavior.
- Text chunking and filename validation.

## 8. Limitations

- The application currently supports `.txt` documents only.
- Uploaded documents are limited to 1 MB.
- Answer quality depends on the uploaded content, retrieval results, and language model.
- The application is a local demonstration rather than a production deployment.
- Hybrid retrieval is optional and disabled in the default configuration.
- The application does not currently provide user accounts or multi-user access management.

---

# Part 2: Reading Summary – Caching Strategies

## 1. Introduction to Caching

Caching is the process of temporarily storing frequently accessed data so that it can be retrieved faster when needed again.

Instead of repeating an expensive operation, an application can check whether the required result is already available in the cache.

Caching can reduce response time, database or processing workload, and resource consumption.

## 2. Caching Strategies

### 2.1 Cache-Aside vs. Read-Through

**Cache-Aside**

In cache-aside, the application is responsible for checking the cache.

1. The application checks whether the requested data exists in the cache.
2. If it exists, the cached result is returned.
3. If it does not exist, the application retrieves the data from the main data source.
4. The application stores the retrieved result in the cache for future requests.

**Advantages:**

- The application controls what gets cached.
- Data is cached only when it is requested.
- The application can handle cache failures separately.

**Disadvantages:**

- The application must implement cache lookup and storage logic.
- The first request may be slower because the data must be retrieved from the main source.

**Read-Through**

In read-through caching, the application requests data from the cache, and the caching layer retrieves missing data from the main data source automatically.

**Advantages:**

- Simplifies application-level retrieval logic.
- The caching layer manages cache population.

**Disadvantages:**

- Requires a caching system that supports read-through behavior.
- The application has less direct control over cache population.

**Comparison:** Cache-aside gives the application more control, while read-through moves more responsibility to the caching layer.

### 2.2 Write-Through, Write-Behind, and Write-Around

**Write-Through**

Every write operation updates both the cache and the main data source.

- Keeps cached and stored data consistent.
- Writes may take longer because both locations must be updated.

**Write-Behind (Write-Back)**

The application writes to the cache first, and changes are written to the main data source later.

- Can improve write performance.
- There is a risk of losing data if cached changes are not written to permanent storage.

**Write-Around**

Data is written directly to the main data source without updating the cache.

- Prevents data that may not be requested again from unnecessarily filling the cache.
- A later read may result in a cache miss.

**Comparison:** Write-through prioritizes consistency, write-behind prioritizes write performance, and write-around avoids caching every write operation.

## 3. Cache Management

### 3.1 Time-to-Live (TTL)

TTL determines how long an item remains in the cache before it expires.

For example, a TTL of 3,600 seconds means that a cached item expires after one hour.

TTL helps prevent cached data from remaining available indefinitely.

### 3.2 Cache Invalidation

Cache invalidation is the process of making cached data unusable when the original data changes.

For example, if a document is updated, an answer generated from its previous content may no longer be accurate.

Invalidation ensures that future requests use information based on the updated document collection.

### 3.3 Cache Eviction

Cache eviction removes existing items when the cache reaches its memory limit.

Different eviction policies determine which items should be removed.

## 4. Cache Eviction Policies

| Policy                      | Description                                                       | Main Consideration                                                         |
| --------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------- |
| LRU (Least Recently Used)   | Removes the item that has not been accessed for the longest time. | Useful when recently accessed items are more likely to be requested again. |
| LFU (Least Frequently Used) | Removes the item with the lowest access frequency.                | Useful when frequently requested items should remain cached.               |
| FIFO (First In, First Out)  | Removes the item that entered the cache first.                    | Does not consider how often or recently an item is accessed.               |
| Random                      | Removes a randomly selected item.                                 | Simple, but does not consider usage patterns.                              |

### 4.1 Redis Eviction Policies

Redis supports several eviction policies:

| Redis Policy      | Description                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------------- |
| `noeviction`      | Does not remove existing keys when the memory limit is reached; new memory-consuming writes are rejected. |
| `allkeys-lru`     | Evicts the least recently used keys from all keys.                                                        |
| `allkeys-lfu`     | Evicts the least frequently used keys from all keys.                                                      |
| `allkeys-random`  | Evicts randomly selected keys from all keys.                                                              |
| `volatile-lru`    | Evicts least recently used keys among keys with an expiration time.                                       |
| `volatile-lfu`    | Evicts least frequently used keys among keys with an expiration time.                                     |
| `volatile-random` | Evicts randomly selected keys among keys with an expiration time.                                         |
| `volatile-ttl`    | Evicts keys with the shortest remaining TTL among keys with an expiration time.                           |

Redis does not provide a standard FIFO eviction policy. Its LRU and LFU implementations use approximations rather than tracking every access perfectly.

## 5. Caching Design in KnowledgeHub

KnowledgeHub uses Redis to store previously generated answers and reduce the time required to respond to repeated questions.

The following decisions were made:

### 5.1 Cache-Aside Strategy

KnowledgeHub uses cache-aside because the application needs to check Redis before searching documents or generating a new answer.

The application controls what gets cached and can continue answering questions if Redis is unavailable.

### 5.2 TTL of One Hour

Cached answers have a default TTL of 3,600 seconds (one hour).

A small random variation of up to 10% is added to expiration times so that many entries do not expire at exactly the same moment.

### 5.3 Cache Invalidation Using Document Versions

The application maintains a document version number in `data/corpus_version.txt`.

Whenever a document is uploaded, replaced, or deleted, this version increases.

The version is included in the cache key. This means answers from an older document collection are no longer used after a document changes.

Old entries are not immediately deleted; they eventually expire or are removed through eviction.

### 5.4 Caching Only Successful Answers

KnowledgeHub caches successful answers to standalone questions, together with their source references.

Follow-up questions are not cached because their meaning can depend on previous conversation messages.

Answers indicating that the documents do not contain enough information are also not cached.

### 5.5 Redis Failure Handling

If Redis becomes unavailable, the application continues retrieving information and generating answers without using the cache.

This prevents a cache failure from making the entire application unavailable.

### 5.6 Eviction Policy: allkeys-lru

KnowledgeHub uses the `allkeys-lru` policy with a 100 MiB memory limit.

Since recently asked questions are more likely to be repeated, LRU is a reasonable choice for keeping useful answers available while removing less recently used entries.

FIFO ignores how frequently an item is accessed, while LFU may keep answers that were popular in the past but are no longer requested.

## 6. Performance Comparison

The application was tested locally using Ollama and Qwen 2.5 3B. After warming up the model, the following response times were observed:

| Request                      |   Response Time |
| ---------------------------- | --------------: |
| Cache MISS 1                 |      8,714.4 ms |
| Cache MISS 2                 |      8,054.7 ms |
| Cache MISS 3                 |     14,455.8 ms |
| **Average MISS**             | **10,408.3 ms** |
| **Average HIT (5 requests)** |      **4.2 ms** |

The average cache HIT was approximately 99.96% faster than the average cache MISS.

These measurements were collected on one local machine and are intended to demonstrate the performance difference between generating a new answer and returning a cached answer. They should not be treated as general performance benchmarks.
