"""
research_agent/tools/pdf_reader.py
────────────────────────────────────
Uploaded PDF ingestion — extracts text, chunks it, returns list of TextChunk objects.
Handles text-based PDFs; falls back gracefully on scanned PDFs.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from pypdf import PdfReader


@dataclass
class TextChunk:
    source:    str          # filename
    page:      int
    chunk_idx: int
    text:      str
    char_count: int


def _clean(text: str) -> str:
    """Remove hyphenation artefacts, normalise whitespace."""
    text = re.sub(r"-\n(\w)", r"\1", text)       # dehyphenate
    text = re.sub(r"\n{3,}", "\n\n", text)        # collapse blank lines
    text = re.sub(r"[ \t]+", " ", text)           # normalise spaces
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 1500, overlap: int = 150) -> list[str]:
    """
    Split text into overlapping chunks of ~chunk_size characters,
    breaking at sentence boundaries where possible.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) > chunk_size and current:
            chunks.append(current.strip())
            # keep overlap from end of previous chunk
            words = current.split()
            current = " ".join(words[-overlap // 6:]) + " " + sent
        else:
            current += " " + sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def read_pdf(
    path: str | Path,
    chunk_size: int = 1500,
    overlap: int = 150,
    max_pages: int | None = None,
) -> list[TextChunk]:
    """
    Read a PDF file and return a list of TextChunk objects.

    Args:
        path:        Path to the PDF file.
        chunk_size:  Target character count per chunk.
        overlap:     Character overlap between consecutive chunks.
        max_pages:   If set, only read the first N pages.

    Returns:
        List of TextChunk objects, empty list if text extraction fails.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    reader   = PdfReader(str(path))
    pages    = reader.pages[:max_pages] if max_pages else reader.pages
    all_text = ""
    page_map: list[tuple[int, int, int]] = []   # (page_num, start_char, end_char)

    for i, page in enumerate(pages):
        raw = page.extract_text() or ""
        clean = _clean(raw)
        start = len(all_text)
        all_text += clean + "\n\n"
        page_map.append((i + 1, start, len(all_text)))

    if not all_text.strip():
        print(f"[pdf_reader] Warning: no extractable text in {path.name} (scanned PDF?)")
        return []

    raw_chunks = _chunk_text(all_text, chunk_size, overlap)

    # Map each chunk back to a page number
    results = []
    for idx, chunk_text in enumerate(raw_chunks):
        char_pos = all_text.find(chunk_text[:50])
        page_num = 1
        for pnum, start, end in page_map:
            if start <= char_pos < end:
                page_num = pnum
                break

        results.append(TextChunk(
            source=path.name,
            page=page_num,
            chunk_idx=idx,
            text=chunk_text,
            char_count=len(chunk_text),
        ))

    return results


def read_pdfs(paths: list[str | Path], **kwargs) -> list[TextChunk]:
    """Read multiple PDFs and return all chunks combined."""
    all_chunks = []
    for p in paths:
        try:
            all_chunks.extend(read_pdf(p, **kwargs))
        except Exception as e:
            print(f"[pdf_reader] Failed to read {p}: {e}")
    return all_chunks
