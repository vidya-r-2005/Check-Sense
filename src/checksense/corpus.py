"""Corpus construction and filtering module for CheckSense.

Parses authentic PURE requirements documents (XML and text), performs sentence
boundary segmentation, applies strict candidate requirement filters (modal verb,
5-60 tokens, non-heading), deduplicates, and logs exact filtering statistics.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

MODAL_PATTERN = re.compile(r"\b(shall|must|should|will)\b", re.IGNORECASE)


def clean_whitespace(text: str) -> str:
    """Normalize internal and external whitespace."""
    return " ".join(text.split())


def split_into_sentences(text: str) -> list[str]:
    """Deterministic sentence splitting on terminal punctuation."""
    cleaned = clean_whitespace(text)
    if not cleaned:
        return []
    # Split on sentence-ending punctuation followed by whitespace and a capital letter or digit
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned)
    return [s.strip() for s in raw_sentences if s.strip()]


def parse_pure_xml_file(xml_path: Path) -> tuple[str, list[str], set[str]]:
    """Parse a single PURE XML document into raw sentences and known headings."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Remove namespace prefixes from tags
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    doc_id = xml_path.stem

    # Extract headings to filter out titles
    known_headings = set()
    for t in root.findall(".//title"):
        t_clean = clean_whitespace("".join(t.itertext())).lower()
        if t_clean:
            known_headings.add(t_clean)

    doc_sentences: list[str] = []

    # Priority 1: Extract from <req> tags if present
    req_elements = root.findall(".//req")
    if req_elements:
        for req in req_elements:
            t = clean_whitespace("".join(req.itertext()))
            if t:
                doc_sentences.extend(split_into_sentences(t))

    # Priority 2: Extract from <p> paragraphs not already containing <req>
    for p in root.findall(".//p"):
        if p.findall(".//req"):
            continue
        for tb in p.findall("./text_body"):
            t = clean_whitespace("".join(tb.itertext()))
            if t:
                doc_sentences.extend(split_into_sentences(t))

    return doc_id, doc_sentences, known_headings


def parse_pure_html_file(html_path: Path) -> tuple[str, list[str], set[str]]:
    """Parse a single PURE HTML specification document into raw sentences and headings."""
    from bs4 import BeautifulSoup

    doc_id = html_path.stem
    content = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")

    known_headings = set()
    for tag in soup.find_all(["title", "h1", "h2", "h3", "h4"]):
        t = clean_whitespace(tag.get_text()).lower()
        if t:
            known_headings.add(t)

    raw_sentences: list[str] = []
    blocks = soup.find_all(["p", "li", "td", "dd"])
    if blocks:
        for block in blocks:
            text = clean_whitespace(block.get_text())
            if text:
                raw_sentences.extend(split_into_sentences(text))
    else:
        text = clean_whitespace(soup.get_text())
        if text:
            raw_sentences.extend(split_into_sentences(text))

    return doc_id, raw_sentences, known_headings


def parse_pure_pdf_file(pdf_path: Path) -> tuple[str, list[str], set[str]]:
    """Parse a single PURE PDF specification document into raw sentences and headings."""
    import pypdf

    doc_id = pdf_path.stem
    reader = pypdf.PdfReader(pdf_path)
    full_text_blocks: list[str] = []
    known_headings: set[str] = set()

    for page in reader.pages:
        page_text = page.extract_text() or ""
        for line in page_text.splitlines():
            cleaned_line = clean_whitespace(line)
            if not cleaned_line:
                continue
            if len(cleaned_line.split()) <= 4 and not cleaned_line.endswith((".", "!", "?", ";", ":")):
                known_headings.add(cleaned_line.lower())
            full_text_blocks.append(cleaned_line)

    full_text = " ".join(full_text_blocks)
    raw_sentences = split_into_sentences(full_text)
    return doc_id, raw_sentences, known_headings


EXTRA_PURE_TARGETS = [
    "1999 - multi-mahjong.html",
    "2005 - nenios.html",
    "2001 - beyond.pdf",
    "2001 - ctc network.pdf",
    "2001 - elsfork.pdf",
    "2001 - esa.pdf",
    "2001 - hats.pdf",
    "2002 - evla back.pdf",
]


def build_pure_corpus(
    input_dir: Path = Path("data/raw/pure/extracted/requirements-xml/XMLZIPFile"),
    output_file: Path = Path("data/interim/pure_requirements.jsonl"),
    stats_file: Path = Path("data/interim/pure_filtering_stats.json"),
    min_tokens: int = 5,
    max_tokens: int = 60,
    include_extra_docs: bool = True,
    extra_docs_dir: Path = Path("data/raw/pure/extracted/requirements/req"),
) -> dict[str, Any]:
    """Parse PURE documents (XML, HTML, PDF), apply filters, and write interim JSONL."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    # Discover XML files, ignoring macOS resource forks
    doc_paths: list[tuple[str, Path]] = [
        ("xml", f) for f in sorted(input_dir.rglob("*.xml"))
        if "__MACOSX" not in f.parts and not f.name.startswith("._")
    ]
    if not doc_paths:
        raise FileNotFoundError(f"No XML files found in {input_dir}")

    # Add extra authentic PURE documents if enabled and available
    if include_extra_docs and extra_docs_dir.exists():
        for filename in EXTRA_PURE_TARGETS:
            extra_file = extra_docs_dir / filename
            if extra_file.is_file():
                kind = "html" if extra_file.suffix.lower() == ".html" else "pdf"
                doc_paths.append((kind, extra_file))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    stats_file.parent.mkdir(parents=True, exist_ok=True)

    total_extracted_sentences = 0
    removed_duplicates = 0
    removed_headings = 0
    removed_no_modal = 0
    removed_too_short = 0
    removed_too_long = 0
    retained_requirements = 0

    per_doc_stats: dict[str, dict[str, int]] = {}
    corpus_rows: list[dict[str, Any]] = []

    for kind, doc_path in doc_paths:
        if kind == "xml":
            doc_id, sentences, headings = parse_pure_xml_file(doc_path)
        elif kind == "html":
            doc_id, sentences, headings = parse_pure_html_file(doc_path)
        elif kind == "pdf":
            doc_id, sentences, headings = parse_pure_pdf_file(doc_path)
        else:
            continue
        raw_count = len(sentences)
        total_extracted_sentences += raw_count

        seen_in_doc: set[str] = set()
        doc_retained = 0
        doc_dups = 0
        doc_headings = 0
        doc_no_modal = 0
        doc_short = 0
        doc_long = 0

        for sent_idx, sentence in enumerate(sentences):
            sent_norm = sentence.lower()

            # 1. Deduplication within document
            if sent_norm in seen_in_doc:
                removed_duplicates += 1
                doc_dups += 1
                continue
            seen_in_doc.add(sent_norm)

            # 2. Heading filter
            is_known_heading = sent_norm in headings
            is_heuristic_heading = (len(sentence.split()) <= 4) and not sentence.endswith((".", "!", "?"))
            if is_known_heading or is_heuristic_heading:
                removed_headings += 1
                doc_headings += 1
                continue

            # 3. Modal verb requirement
            if not MODAL_PATTERN.search(sentence):
                removed_no_modal += 1
                doc_no_modal += 1
                continue

            # 4. Token length boundaries [5, 60]
            tokens = sentence.split()
            token_count = len(tokens)
            if token_count < min_tokens:
                removed_too_short += 1
                doc_short += 1
                continue
            if token_count > max_tokens:
                removed_too_long += 1
                doc_long += 1
                continue

            # Passed all filters: Candidate functional requirement
            req_id = f"{doc_id}_sent_{sent_idx:04d}"
            record = {
                "req_id": req_id,
                "doc_id": doc_id,
                "text": sentence,
                "source_file": doc_path.name,
                "sent_idx": sent_idx,
                "token_count": token_count,
            }
            corpus_rows.append(record)
            doc_retained += 1
            retained_requirements += 1

        per_doc_stats[doc_id] = {
            "source_file": doc_path.name,
            "raw_sentences": raw_count,
            "removed_duplicates": doc_dups,
            "removed_headings": doc_headings,
            "removed_no_modal": doc_no_modal,
            "removed_too_short": doc_short,
            "removed_too_long": doc_long,
            "retained_requirements": doc_retained,
        }

    # Write JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for row in corpus_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    audit_stats: dict[str, Any] = {
        "summary": {
            "total_documents_processed": len(doc_paths),
            "documents_dropped": 0,
            "total_raw_sentences_extracted": total_extracted_sentences,
            "removed_duplicates": removed_duplicates,
            "removed_headings": removed_headings,
            "removed_no_modal_verb": removed_no_modal,
            "removed_too_short_lt5": removed_too_short,
            "removed_too_long_gt60": removed_too_long,
            "total_candidate_requirements_retained": retained_requirements,
            "modal_filter_retention_rate": (
                round(retained_requirements / (total_extracted_sentences - removed_duplicates), 4)
                if (total_extracted_sentences - removed_duplicates) > 0
                else 0.0
            ),
        },
        "per_document_breakdown": per_doc_stats,
    }

    stats_file.write_text(json.dumps(audit_stats, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print("PURE Corpus Build Complete")
    print(f"{'='*60}")
    print(f"Total documents processed: {len(doc_paths)} (0 dropped)")
    print(f"Total raw sentences:        {total_extracted_sentences}")
    print(f"Removed duplicates:         {removed_duplicates}")
    print(f"Removed headings:           {removed_headings}")
    print(f"Removed no modal verb:      {removed_no_modal}")
    print(f"Removed < 5 tokens:         {removed_too_short}")
    print(f"Removed > 60 tokens:        {removed_too_long}")
    print(f"Retained requirements:      {retained_requirements}")
    print(f"Output JSONL:               {output_file} ({output_file.stat().st_size:,} bytes)")
    print(f"Filtering Audit Log:        {stats_file}")
    print(f"{'='*60}\n")

    return audit_stats
