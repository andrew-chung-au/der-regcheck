"""Extract page-preserving PDF text and main-content HTML from the DER RegCheck corpus.

This extractor only processes sources marked eligible_for_extraction=true in
corpus_metadata.json. Sources that failed validation or are pending manual
review are logged as skipped rather than causing the pipeline to fail.

Usage:
    uv add pypdf beautifulsoup4 requests
    uv run python src/ingestion/extract_raw_content.py

Input:
    data/corpus/corpus_metadata.json
    data/corpus/<downloaded source files>

Output:
    data/processed/extracted/<document_id>.json
    data/processed/extraction_manifest.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag
from pypdf import PdfReader


EXTRACTION_SCHEMA_VERSION = "1.0"
PDF_EXTRACTION_METHOD = "pypdf_page_text"
HTML_EXTRACTION_METHOD = "beautifulsoup_main_content_blocks"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = PROJECT_ROOT / "data" / "corpus"
CORPUS_METADATA_PATH = CORPUS_DIR / "corpus_metadata.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "extracted"
MANIFEST_PATH = PROJECT_ROOT / "data" / "processed" / "extraction_manifest.json"

CONTENT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "button"}
REMOVABLE_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside", "form"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalise_text(value: str) -> str:
    return " ".join(value.split())


def resolve_local_path(source: dict[str, Any]) -> Path:
    path = Path(source["local_path"])
    return path if path.is_absolute() else PROJECT_ROOT / path


def find_main_content(soup: BeautifulSoup) -> Tag:
    main = soup.find("main")
    if main:
        return main

    role_main = soup.find(attrs={"role": "main"})
    if role_main:
        return role_main

    for class_name in ("c-main", "main-content", "page-content", "content"):
        node = soup.find(class_=lambda classes: classes and class_name in classes)
        if node:
            return node

    return soup.body or soup


def nearest_content_parent(element: Tag) -> Tag | None:
    parent = element.parent
    while isinstance(parent, Tag):
        if parent.name in CONTENT_TAGS:
            return parent
        parent = parent.parent
    return None


def render_inline(element: Tag, base_url: str) -> str:
    parts: list[str] = []
    for node in element.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag) and node.name == "a":
            label = normalise_text(node.get_text(" ", strip=True))
            href = node.get("href")
            if label and href:
                parts.append(f" [{label}]({urljoin(base_url, href)}) ")
    return normalise_text(" ".join(parts))


def table_to_markdown(table: Tag, base_url: str) -> str:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [
            render_inline(cell, base_url)
            for cell in tr.find_all(["th", "td"], recursive=False)
        ]
        if cells:
            rows.append(cells)

    if not rows:
        return normalise_text(table.get_text(" ", strip=True))

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    separator = ["---"] * width
    body = rows[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def html_blocks(html_path: Path, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    main = find_main_content(soup)

    for node in main.find_all(REMOVABLE_TAGS):
        node.decompose()

    blocks: list[dict[str, Any]] = []
    active_headings: dict[int, str] = {}

    for element in main.find_all(CONTENT_TAGS):
        if element.name != "li" and nearest_content_parent(element) is not None:
            continue

        is_accordion = (
            element.name == "button"
            and "accordion" in " ".join(element.get("class", [])).lower()
        )
        if element.name == "button" and not is_accordion:
            continue

        if element.name.startswith("h") or is_accordion:
            level = int(element.name[1]) if element.name.startswith("h") else 3
            heading = normalise_text(element.get_text(" ", strip=True))
            if not heading:
                continue
            active_headings = {
                key: value for key, value in active_headings.items() if key < level
            }
            active_headings[level] = heading
            blocks.append(
                {
                    "block_type": "heading",
                    "heading_level": level,
                    "heading": heading,
                    "heading_path": " > ".join(
                        active_headings[key] for key in sorted(active_headings)
                    ),
                    "text": heading,
                }
            )
            continue

        if element.name == "table":
            text = table_to_markdown(element, source_url)
            block_type = "table"
        elif element.name == "li":
            text = "- " + render_inline(element, source_url)
            block_type = "list_item"
        else:
            text = render_inline(element, source_url)
            block_type = "paragraph"

        if text:
            blocks.append(
                {
                    "block_type": block_type,
                    "heading_path": " > ".join(
                        active_headings[key] for key in sorted(active_headings)
                    ),
                    "text": text,
                }
            )

    return blocks


def extract_pdf(source: dict[str, Any], input_path: Path) -> dict[str, Any]:
    reader = PdfReader(input_path)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(
            {
                "page_number": page_number,
                "text": text,
                "marker": f"--- PAGE {page_number} ---",
            }
        )

    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "document_id": source["id"],
        "source_type": "pdf",
        "extraction_method": PDF_EXTRACTION_METHOD,
        "extracted_at": now_iso(),
        "page_count": len(pages),
        "pages": pages,
        "structured_text": "\n\n".join(
            f"{page['marker']}\n{page['text']}" for page in pages
        ),
    }


def extract_html(source: dict[str, Any], input_path: Path) -> dict[str, Any]:
    blocks = html_blocks(input_path, source["url"])
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "document_id": source["id"],
        "source_type": "html",
        "extraction_method": HTML_EXTRACTION_METHOD,
        "extracted_at": now_iso(),
        "blocks": blocks,
        "structured_text": "\n\n".join(
            block["text"]
            if block["block_type"] != "heading"
            else f"--- H{block['heading_level']}: {block['heading']} ---"
            for block in blocks
        ),
    }


def extract_source(source: dict[str, Any]) -> dict[str, Any]:
    if not source.get("eligible_for_extraction", False):
        raise ValueError(
            f"Source {source['id']} is not eligible for extraction. "
            f"automated_validation.status="
            f"{source.get('automated_validation', {}).get('status')}, "
            f"manual_review.status="
            f"{source.get('manual_review', {}).get('status')}"
        )

    input_path = resolve_local_path(source)
    if not input_path.exists():
        raise FileNotFoundError(f"Downloaded source not found: {input_path}")

    if source["type"] == "pdf":
        extraction = extract_pdf(source, input_path)
    elif source["type"] == "html":
        extraction = extract_html(source, input_path)
    else:
        raise ValueError(f"Unsupported source type: {source['type']}")

    extraction["source"] = {
        "id": source["id"],
        "title": source["title"],
        "url": source["url"],
        "source_org": source["source_org"],
        "content_hash": source.get("content_hash"),
        "last_checked": source.get("last_checked"),
        "is_current": source.get("is_current"),
    }
    return extraction


def main() -> None:
    if not CORPUS_METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Corpus metadata not found: {CORPUS_METADATA_PATH}. "
            "Run the downloader first."
        )

    metadata = json.loads(CORPUS_METADATA_PATH.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "extracted_at": now_iso(),
        "documents": [],
        "failures": [],
        "skipped": [],
    }

    for source in metadata.get("sources", []):
        if not source.get("eligible_for_extraction", False):
            manifest["skipped"].append(
                {
                    "document_id": source["id"],
                    "reason": "not_eligible_for_extraction",
                    "validation_status": source.get("automated_validation", {}).get(
                        "status"
                    ),
                    "manual_review_status": source.get("manual_review", {}).get(
                        "status"
                    ),
                }
            )
            print(f"SKIPPED (not eligible): {source['id']}")
            continue

        try:
            extraction = extract_source(source)
            output_path = OUTPUT_DIR / f"{source['id']}.json"
            output_path.write_text(
                json.dumps(extraction, indent=2), encoding="utf-8"
            )
            manifest["documents"].append(
                {
                    "document_id": source["id"],
                    "status": "success",
                    "output_path": str(output_path.relative_to(PROJECT_ROOT)),
                    "source_hash": source.get("content_hash"),
                    "schema_version": extraction["schema_version"],
                    "extraction_method": extraction["extraction_method"],
                    "extracted_at": extraction["extracted_at"],
                }
            )
            print(f"Extracted: {source['id']} -> {output_path}")
        except Exception as error:
            manifest["failures"].append(
                {
                    "document_id": source.get("id"),
                    "status": "failed",
                    "error": str(error),
                    "failed_at": now_iso(),
                }
            )
            print(f"FAILED: {source.get('id')}: {error}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Extraction manifest: {MANIFEST_PATH}")

    if manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
