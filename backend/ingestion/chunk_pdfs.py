"""
chunk_pdfs.py — Extract text + tables from PDFs, produce chunks.json.

Rules:
- Tables are converted to markdown and never split across chunks.
- Deprecated policy file is tagged with is_deprecated=True.
- Each chunk carries: chunk_id, source_file, page, text, is_deprecated.
- Target chunk size ~400 tokens (≈ 1600 chars); 50-token overlap (≈ 200 chars).
"""

import json
from pathlib import Path

import pdfplumber

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
OUT_FILE = Path(__file__).parent.parent / "data" / "processed" / "chunks.json"

CHUNK_SIZE = 1600   # chars (~400 tokens)
OVERLAP = 200       # chars (~50 tokens)

# Files that must be flagged as deprecated — never cite these as authority
DEPRECATED_FILES = {"02_Support_Policy_v2_DEPRECATED.pdf"}

PDF_FILES = [
    "01_Support_Policy_v3_CURRENT.pdf",
    "02_Support_Policy_v2_DEPRECATED.pdf",
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf",
    "04_Product_Operations_Guide_and_Known_Issues.pdf",
    "05_Northstar_Logistics_Enterprise_Agreement.pdf",
    "06_LumenWorks_Service_Agreement.pdf",
]


def table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table (list of rows) to a markdown table string."""
    if not table or not table[0]:
        return ""
    # Use first row as header
    header = [str(cell or "").strip() for cell in table[0]]
    rows = [[str(cell or "").strip() for cell in row] for row in table[1:]]
    sep = ["---"] * len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        # Pad short rows
        while len(row) < len(header):
            row.append("")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extract_page_content(page) -> list[dict]:
    """
    Return a list of content blocks for a single page.
    Each block is {"type": "text"|"table", "text": str}.
    Tables are extracted first (by bbox) so text extraction can skip table regions.
    """
    blocks = []
    tables = page.find_tables()
    table_bboxes = [t.bbox for t in tables]

    # Extract text outside table bounding boxes
    if table_bboxes:
        # Crop out table areas and extract remaining text
        non_table_text = page.filter(
            lambda obj: not any(
                obj["x0"] >= bbox[0] and obj["top"] >= bbox[1]
                and obj["x1"] <= bbox[2] and obj["bottom"] <= bbox[3]
                for bbox in table_bboxes
            )
        ).extract_text() or ""
    else:
        non_table_text = page.extract_text() or ""

    if non_table_text.strip():
        blocks.append({"type": "text", "text": non_table_text.strip()})

    for t in tables:
        md = table_to_markdown(t.extract())
        if md:
            blocks.append({"type": "table", "text": md})

    return blocks


def split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split plain text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]


def process_pdf(pdf_path: Path) -> list[dict]:
    """Process a single PDF, return list of chunk dicts."""
    chunks = []
    chunk_idx = 0
    is_deprecated = pdf_path.name in DEPRECATED_FILES
    source = pdf_path.name

    with pdfplumber.open(pdf_path) as pdf:
        text_buffer = ""
        buffer_page = 1

        for page_num, page in enumerate(pdf.pages, start=1):
            blocks = extract_page_content(page)

            for block in blocks:
                if block["type"] == "table":
                    # Flush any buffered text first
                    if text_buffer.strip():
                        for chunk_text in split_text_into_chunks(text_buffer, CHUNK_SIZE, OVERLAP):
                            chunks.append({
                                "chunk_id": f"{source}::chunk_{chunk_idx}",
                                "source_file": source,
                                "page": buffer_page,
                                "text": chunk_text,
                                "is_deprecated": is_deprecated,
                                "content_type": "text",
                            })
                            chunk_idx += 1
                        text_buffer = ""

                    # Tables are always their own atomic chunk (never split)
                    chunks.append({
                        "chunk_id": f"{source}::chunk_{chunk_idx}",
                        "source_file": source,
                        "page": page_num,
                        "text": block["text"],
                        "is_deprecated": is_deprecated,
                        "content_type": "table",
                    })
                    chunk_idx += 1

                else:  # plain text block
                    text_buffer += "\n" + block["text"]
                    buffer_page = page_num

            # Flush at end of each page if buffer is large enough
            if len(text_buffer) >= CHUNK_SIZE:
                for chunk_text in split_text_into_chunks(text_buffer, CHUNK_SIZE, OVERLAP):
                    chunks.append({
                        "chunk_id": f"{source}::chunk_{chunk_idx}",
                        "source_file": source,
                        "page": buffer_page,
                        "text": chunk_text,
                        "is_deprecated": is_deprecated,
                        "content_type": "text",
                    })
                    chunk_idx += 1
                text_buffer = ""

        # Final flush
        if text_buffer.strip():
            for chunk_text in split_text_into_chunks(text_buffer, CHUNK_SIZE, OVERLAP):
                chunks.append({
                    "chunk_id": f"{source}::chunk_{chunk_idx}",
                    "source_file": source,
                    "page": buffer_page,
                    "text": chunk_text,
                    "is_deprecated": is_deprecated,
                    "content_type": "text",
                })
                chunk_idx += 1

    return chunks


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    all_chunks = []

    for fname in PDF_FILES:
        path = RAW_DIR / fname
        if not path.exists():
            print(f"[WARN] Missing: {path} — skipping")
            continue
        print(f"Processing {fname} ...", end=" ")
        chunks = process_pdf(path)
        print(f"{len(chunks)} chunks")
        all_chunks.extend(chunks)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Saved -> {OUT_FILE}")


if __name__ == "__main__":
    main()
