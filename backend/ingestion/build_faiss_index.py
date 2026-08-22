"""
build_faiss_index.py — Embed chunks.json with sentence-transformers, save FAISS index.

Model: all-MiniLM-L6-v2 (fast, lightweight, good for short passages).
Output:
  indexes/faiss_index/index.faiss  — the FAISS binary index
  indexes/faiss_index/chunk_ids.json — ordered list of chunk_ids (position = FAISS row)
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS_FILE = Path(__file__).parent.parent / "data" / "processed" / "chunks.json"
INDEX_DIR = Path(__file__).parent.parent / "indexes" / "faiss_index"
EMBED_MODEL = "all-MiniLM-L6-v2"


def main():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks. Embedding...")

    model = SentenceTransformer(EMBED_MODEL)
    texts = [c["text"] for c in chunks]
    chunk_ids = [c["chunk_id"] for c in chunks]

    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    # Normalize for cosine similarity via inner product
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # Inner product on L2-normalised = cosine
    index.add(embeddings)

    faiss.write_index(index, str(INDEX_DIR / "index.faiss"))

    with open(INDEX_DIR / "chunk_ids.json", "w", encoding="utf-8") as f:
        json.dump(chunk_ids, f)

    print(f"FAISS index saved -> {INDEX_DIR}/index.faiss  ({len(chunk_ids)} vectors, dim={dim})")


if __name__ == "__main__":
    main()
