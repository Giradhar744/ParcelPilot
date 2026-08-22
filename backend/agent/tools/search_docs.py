"""
search_docs.py — Hybrid retrieval: FAISS (dense) + BM25 (keyword) over policy/contract chunks.

Returns the top-k unique chunks by unioning both result sets.
Deprecated chunks are filtered out before returning.
"""

import json
import pickle
from pathlib import Path

import os
import numpy as np

BASE = Path(__file__).parent.parent.parent  # backend/
CHUNKS_FILE = BASE / "data" / "processed" / "chunks.json"
FAISS_DIR = BASE / "indexes" / "faiss_index"
BM25_FILE = BASE / "indexes" / "bm25_index.pkl"

EMBED_MODEL = "all-MiniLM-L6-v2"
TOP_K = 5   # results per retrieval path (union may return up to 2*TOP_K, deduped)

# Module-level singletons — loaded once, reused across requests
_chunks: list[dict] | None = None
_chunk_map: dict[str, dict] | None = None
_faiss_index = None
_faiss_ids: list[str] | None = None
_bm25 = None
_bm25_ids: list[str] | None = None
_embed_model = None
faiss = None  # Dynamically imported in _load()


def _load():
    global _chunks, _chunk_map, _faiss_index, _faiss_ids, _bm25, _bm25_ids, _embed_model, faiss

    if _chunks is not None:
        return  # already loaded

    # 1. Limit CPU/thread memory footprint of deep learning libs
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"

    # 2. Lazy imports to keep uvicorn startup extremely light
    import faiss as faiss_module
    faiss = faiss_module
    
    from sentence_transformers import SentenceTransformer
    import torch
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)

    # 3. Load files
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        _chunks = json.load(f)
    _chunk_map = {c["chunk_id"]: c for c in _chunks}

    _faiss_index = faiss.read_index(str(FAISS_DIR / "index.faiss"))
    with open(FAISS_DIR / "chunk_ids.json", encoding="utf-8") as f:
        _faiss_ids = json.load(f)

    with open(BM25_FILE, "rb") as f:
        data = pickle.load(f)
    _bm25 = data["bm25"]
    _bm25_ids = data["chunk_ids"]

    _embed_model = SentenceTransformer(EMBED_MODEL)



# Map account_id to the specific agreement filename they are authorized to access.
CONTRACT_MAP = {
    "ACCT-001": "05_Northstar_Logistics_Enterprise_Agreement.pdf",
    "ACCT-002": "06_LumenWorks_Service_Agreement.pdf",
}


def search_docs(query: str, account_id: str, top_k: int = TOP_K) -> list[dict]:
    """
    Hybrid search: FAISS cosine + BM25, union result sets, deduplicate, filter deprecated,
    and enforce account-scoping so that custom contracts belonging to other users are excluded.
    """
    _load()

    global faiss
    if faiss is None:
        import faiss as faiss_module
        faiss = faiss_module

    # ── Dense retrieval (FAISS) ──────────────────────────────────────────────
    q_vec = _embed_model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(q_vec)
    _, faiss_indices = _faiss_index.search(q_vec, top_k)
    dense_ids = {_faiss_ids[i] for i in faiss_indices[0] if i >= 0}

    # ── Keyword retrieval (BM25) ─────────────────────────────────────────────
    tokens = query.lower().split()
    scores = _bm25.get_scores(tokens)
    # Top-k by BM25 score
    ranked_bm25 = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    keyword_ids = {_bm25_ids[i] for i, s in ranked_bm25 if s > 0}

    # ── Union + Access Filter ────────────────────────────────────────────────
    all_ids = dense_ids | keyword_ids
    results = []

    allowed_contract = CONTRACT_MAP.get(account_id)

    for cid in all_ids:
        if cid not in _chunk_map:
            continue
        chunk = _chunk_map[cid]

        # 1. Skip deprecated chunks
        if chunk.get("is_deprecated", False):
            continue

        # 2. Enforce account-level contract security scoping
        src = chunk.get("source_file", "")
        # If document is a contract/service agreement (05_* or 06_*)
        if "Agreement" in src or src.startswith("05_") or src.startswith("06_"):
            if account_id != "INTERNAL-OPERATIONS" and src != allowed_contract:
                # Silently drop chunk from other customer's contract
                continue

        results.append(chunk)

    return results


# Tool schema for the LLM
SEARCH_DOCS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_docs",
        "description": (
            "Search the policy documents and customer contracts for relevant information. "
            "Use this to answer questions about SLAs, cancellation policy, service credits, "
            "known issues, and account-specific contract terms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query — use specific terms, order IDs, or policy keywords.",
                },
            },
            "required": ["query"],
        },
    },
}
