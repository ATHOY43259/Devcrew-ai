"""Shared vector knowledge base (RAG) — REAL implementation. Owner: Member 2.

This is the project's long-term memory (rubric: Memory 10 marks + shared
knowledge base requirement). Short-term memory is the graph state itself +
the LangGraph checkpointer.

Backed by a persistent Chroma collection at ./memory_store, using Chroma's
built-in local embedding function (ONNX MiniLM) — deliberately NOT
OpenAIEmbeddings, so the knowledge base works even in mock mode / without an
API key. Only the chat LLM calls (call_llm) need OPENAI_API_KEY.
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

STORE_DIR = Path(__file__).resolve().parents[2] / "memory_store"
COLLECTION_NAME = "devcrew_kb"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@lru_cache(maxsize=1)
def _collection():
    import chromadb

    client = chromadb.PersistentClient(path=str(STORE_DIR))
    return client.get_or_create_collection(COLLECTION_NAME)


def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


def add_document(doc_id: str, text: str, metadata: Dict | None = None) -> None:
    """Chunk, embed, and upsert `text` into the persistent collection."""
    chunks = _chunk(text)
    if not chunks:
        return
    collection = _collection()
    base_meta = metadata or {}
    collection.upsert(
        ids=[f"{doc_id}::{i}" for i in range(len(chunks))],
        documents=chunks,
        metadatas=[{**base_meta, "doc_id": doc_id, "chunk": i} for i in range(len(chunks))],
    )


def search(query: str, k: int = 3) -> List[Dict]:
    """Return the k most relevant chunks across all stored documents."""
    collection = _collection()
    if collection.count() == 0:
        return []
    result = collection.query(query_texts=[query], n_results=min(k, collection.count()))
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    return [{"text": doc, "metadata": meta} for doc, meta in zip(docs, metas)]


def all_documents() -> List[Dict]:
    """For the UI's Memory viewer tab."""
    collection = _collection()
    if collection.count() == 0:
        return []
    result = collection.get()
    return [
        {"id": doc_id, "text": text, "metadata": meta}
        for doc_id, text, meta in zip(result["ids"], result["documents"], result["metadatas"])
    ]
