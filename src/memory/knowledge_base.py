"""Shared vector knowledge base (RAG) — STUB. Owner: Member 2.

This is the project's long-term memory (rubric: Memory 10 marks + shared
knowledge base requirement). Short-term memory is the graph state itself +
the LangGraph checkpointer.

TODO(Member 2): implement with Chroma (chromadb + langchain-chroma):
  1. add_document(doc_id, text, metadata): chunk (~800 chars, 100 overlap),
     embed (OpenAIEmbeddings), upsert into a persistent collection at
     ./memory_store.
  2. search(query, k=3) -> list[{"text": ..., "metadata": ...}].
  3. Call add_document from requirements_analyst / architect / doc_writer;
     call search from developer / doc_writer to ground their prompts (RAG).
  4. Expose all_documents() for the UI's Memory viewer tab.
"""
from typing import Dict, List


def add_document(doc_id: str, text: str, metadata: Dict | None = None) -> None:
    raise NotImplementedError("Member 2: implement add_document with Chroma.")


def search(query: str, k: int = 3) -> List[Dict]:
    raise NotImplementedError("Member 2: implement search with Chroma.")


def all_documents() -> List[Dict]:
    """For the UI memory viewer."""
    raise NotImplementedError("Member 2: implement all_documents.")
