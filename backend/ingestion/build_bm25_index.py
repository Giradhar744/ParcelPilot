"""
build_bm25_index.py — Build BM25Okapi index from chunks.json, save as pickle.

Output: indexes/bm25_index.pkl
  Contains a dict:
    {
      "bm25": BM25Okapi instance,
      "chunk_ids": [str, ...]   # same order as BM25 corpus
    }
"""

import json
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

CHUNKS_FILE = Path(__file__).parent.parent / "data" / "processed" / "chunks.json"
INDEX_FILE = Path(__file__).parent.parent / "indexes" / "bm25_index.pkl"


def tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer — sufficient for BM25 term matching."""
    return text.lower().split()


def main():
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks. Building BM25 index...")

    corpus = [tokenize(c["text"]) for c in chunks]
    chunk_ids = [c["chunk_id"] for c in chunks]

    bm25 = BM25Okapi(corpus)

    with open(INDEX_FILE, "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": chunk_ids}, f)

    print(f"BM25 index saved -> {INDEX_FILE}")


if __name__ == "__main__":
    main()
