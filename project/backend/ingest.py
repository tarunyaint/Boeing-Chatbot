"""
ingest.py
Reads data/manual.txt, splits it into overlapping chunks,
extracts keywords, and stores everything in the database.

Run ONCE before starting the server:
    python ingest.py
"""

import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Path to manual — two levels up from backend/
BASE_DIR    = Path(__file__).resolve().parent.parent
MANUAL_PATH = BASE_DIR / "data" / "manual.txt"

CHUNK_SIZE    = 900   # characters per chunk
CHUNK_OVERLAP = 150   # overlap between chunks (avoids cutting mid-sentence)

# ── Chapter detection ────────────────────────────────────────
CHAPTER_PATTERNS = [
    (r"Chapter\s+1\b",              "Chapter 1 — General Information & Safety"),
    (r"Chapter\s+2\b|ATA\s*20\b",   "Chapter 2 — Standard Practices (ATA 20)"),
    (r"Chapter\s+3\b|ATA\s*53\b",   "Chapter 3 — Fuselage Repair (ATA 53)"),
    (r"Chapter\s+4\b|ATA\s*57\b",   "Chapter 4 — Wing Structure Repair (ATA 57)"),
    (r"Chapter\s+5\b|ATA\s*32\b",   "Chapter 5 — Landing Gear (ATA 32)"),
    (r"Chapter\s+6\b|ATA\s*7[12]\b","Chapter 6 — Engine & Nacelle (ATA 71/72)"),
    (r"Chapter\s+7\b|ATA\s*27\b",   "Chapter 7 — Flight Controls (ATA 27)"),
    (r"Chapter\s+8\b|ATA\s*29\b",   "Chapter 8 — Hydraulic Systems (ATA 29)"),
    (r"Chapter\s+9\b|ATA\s*24\b",   "Chapter 9 — Electrical Systems (ATA 24)"),
    (r"Chapter\s+10\b|ATA\s*2[34]\b","Chapter 10 — Avionics (ATA 23/34)"),
    (r"Appendix\s+A\b",             "Appendix A — Torque Tables"),
    (r"Appendix\s+B\b",             "Appendix B — Abbreviations"),
    (r"Appendix\s+C\b",             "Appendix C — References"),
]

SECTION_RE = re.compile(r"^#{1,3}\s+\*?\*?(\d+\.\d+[^\n]*?)\*?\*?$", re.MULTILINE)

STOP_WORDS = {
    "the","a","an","and","or","of","to","in","is","are","be","for","with","this",
    "that","it","as","at","by","on","not","from","per","if","shall","must","may",
    "should","will","can","do","no","all","any","each","such","used","use","using",
    "after","before","when","where","which","who","how","its","their","they","been",
    "has","have","had","was","were","than","then","into","only","also","both","more",
    "most","other","some","these","those","during","through","between","within","without",
}


def detect_chapter(text):
    for pattern, name in CHAPTER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return None


def detect_section(text):
    m = SECTION_RE.search(text)
    return m.group(1).strip() if m else None


def extract_keywords(text):
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    seen, keywords = set(), []
    for t in tokens:
        if t not in STOP_WORDS and t not in seen:
            seen.add(t)
            keywords.append(t)
    return keywords[:60]


def chunk_text(text):
    start  = 0
    length = len(text)
    while start < length:
        end = min(start + CHUNK_SIZE, length)
        yield text[start:end]
        if end == length:
            break
        start = end - CHUNK_OVERLAP


def ingest():
    if not MANUAL_PATH.exists():
        print(f"[ERROR] Manual not found: {MANUAL_PATH}")
        sys.exit(1)

    print(f"Reading manual: {MANUAL_PATH}")
    text = MANUAL_PATH.read_text(encoding="utf-8")
    print(f"  Size: {len(text):,} characters")

    from db import get_db
    db = get_db()

    print("Clearing existing chunks...")
    db.clear_chunks()

    current_chapter = "Front Matter"
    current_section = None
    total = 0

    print("Chunking and indexing...")
    for chunk in chunk_text(text):
        ch = detect_chapter(chunk)
        if ch:
            current_chapter = ch
        sec = detect_section(chunk)
        if sec:
            current_section = sec

        keywords = extract_keywords(chunk)
        db.insert_chunk(current_chapter, current_section, chunk, keywords)
        total += 1

        if total % 50 == 0:
            print(f"  {total} chunks stored...")

    print(f"\nDone — {total} chunks indexed in {db.__class__.__name__}")
    print("You can now run:  python app.py")


if __name__ == "__main__":
    ingest()
