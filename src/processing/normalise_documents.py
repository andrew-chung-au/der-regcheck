"""Normalise DER RegCheck raw extraction outputs into auditable content blocks.

This stage is deterministic. It does not download sources, call an LLM, chunk text,
or decide source authority. Raw extraction outputs remain unchanged in
``data/processed/extracted``.

Usage:
    uv add pyyaml
    uv run python src/processing/normalise_documents.py \
      --input-manifest data/processed/extraction_manifest.json \
      --config config/normalisation.yaml \
      --output-dir data/processed/normalised
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


NORMALISATION_SCHEMA_VERSION = "1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "data" / "processed" / "extraction_manifest.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "normalisation.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "normalised"

PRINTED_PAGE_PATTERN = re.compile(
    r"^(?:Part\s+\d+\s*\|\s*)?P\s*a\s*g\s*e\s+([\w.-]+)$",
    re.IGNORECASE,
)
SECTION_ID_PATTERN = re.compile(r"^(\d+(?:\.\d+){1,4})\s+(.+)$")

TARIFF_RULE_SHEET_PATTERN = re.compile(
    r"\bRule\s+21\s+Sheet\s+(\d+)\b",
    re.IGNORECASE,
)
TARIFF_CPUC_SHEET_PATTERN = re.compile(
    r"\b(?:Original|Revised)\s+Cal\.\s+PUC\s+Sheet\s+No\.\s+(\d+(?:-[A-Z])?)",
    re.IGNORECASE,
)
TARIFF_EFFECTIVE_DATE_PATTERN = re.compile(
    r"\bEffective\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\b"
)
TARIFF_ADVICE_PATTERN = re.compile(
    r"\bAdvice\s+(\d+(?:-[A-Z])?)\b",
    re.IGNORECASE,
)
TARIFF_LETTER_SECTION_PATTERN = re.compile(r"^([A-P])\.\s+(.+)$")
TARIFF_NUMBERED_HEADING_PATTERN = re.compile(r"^(\d+)\.\s+(.+)$")
TARIFF_LETTER_HEADING_PATTERN = re.compile(r"^([a-z]{1,2})\.\s+(.+)$")
TARIFF_ROMAN_LIST_ITEM_PATTERN = re.compile(
    r"^([ivxlcdm]+)\)\s+(.+)$",
    re.IGNORECASE,
)
TARIFF_APPENDIX_PATTERN = re.compile(r"^APPENDIX\s+([A-Z])$", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalise_whitespace(value: str) -> str:
    return " ".join(value.split())


def heading_path_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [normalise_whitespace(item) for item in value if normalise_whitespace(item)]
    if not value:
        return []
    return [
        normalise_whitespace(item)
        for item in value.split(" > ")
        if normalise_whitespace(item)
    ]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def source_config(config: dict[str, Any], source_id: str) -> dict[str, Any]:
    merged = dict(config.get("default", {}))
    merged.update(config.get("sources", {}).get(source_id, {}))
    return merged


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


def line_matches_any(line: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(line) for pattern in patterns)


def block_id(document_id: str, ordinal: int, pdf_page: int | None = None) -> str:
    location = f":p{pdf_page:03d}" if pdf_page is not None else ""
    return f"{document_id}{location}:b{ordinal:04d}"


def make_block(
    *,
    document: dict[str, Any],
    ordinal: int,
    block_type: str,
    text: str,
    heading_path: list[str],
    citation: dict[str, Any],
    flags: list[str] | None = None,
    heading_level: int | None = None,
    heading: str | None = None,
    is_substantive: bool | None = None,
) -> dict[str, Any]:
    pdf_page = citation.get("pdf_page_start")
    result: dict[str, Any] = {
        "block_id": block_id(document["document_id"], ordinal, pdf_page),
        "document_id": document["document_id"],
        "source_id": document["source"]["id"],
        "source_hash": document["source"].get("content_hash"),
        "ordinal": ordinal,
        "block_type": block_type,
        "text": text,
        "heading_path": heading_path,
        "citation": citation,
        "is_substantive": block_type != "boilerplate"
        if is_substantive is None
        else is_substantive,
        "normalisation_flags": flags or [],
    }
    if heading_level is not None:
        result["heading_level"] = heading_level
    if heading is not None:
        result["heading"] = heading
    return result


def normalise_html_document(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    ordinal = 0
    duplicates_suppressed = 0
    drop_paths = set(config.get("drop_heading_paths", []))
    drop_text = set(config.get("drop_exact_text", []))
    previous_key: tuple[str, str, tuple[str, ...]] | None = None

    for raw_block in document.get("blocks", []):
        raw_text = raw_block.get("text", "")
        text = raw_text if raw_block.get("block_type") == "table" else normalise_whitespace(raw_text)
        path = heading_path_list(raw_block.get("heading_path"))
        block_type = raw_block.get("block_type", "unknown")

        if not text:
            continue
        if " > ".join(path) in drop_paths or text in drop_text:
            continue

        key = (block_type, text, tuple(path))
        if key == previous_key:
            duplicates_suppressed += 1
            continue

        ordinal += 1
        blocks.append(
            make_block(
                document=document,
                ordinal=ordinal,
                block_type=block_type,
                text=text,
                heading_path=path,
                citation={"heading_path": path},
                heading_level=raw_block.get("heading_level"),
                heading=raw_block.get("heading"),
            )
        )
        previous_key = key

    return {
        "schema_version": NORMALISATION_SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source_type": "html",
        "normalised_at": now_iso(),
        "normalisation_method": "deterministic_html_block_normalisation",
        "source": document["source"],
        "blocks": blocks,
        "normalisation_summary": {
            "input_blocks": len(document.get("blocks", [])),
            "output_blocks": len(blocks),
            "adjacent_duplicates_suppressed": duplicates_suppressed,
            "blocks_flagged_for_review": 0,
        },
    }


def detect_printed_page_label(lines: list[str]) -> str | None:
    for raw_line in lines[:8]:
        line = normalise_whitespace(raw_line)
        if PRINTED_PAGE_PATTERN.match(line):
            return line
    return None


def detect_heading(line: str, config: dict[str, Any]) -> tuple[int, str, str | None] | None:
    value = normalise_whitespace(line)
    if not value:
        return None

    for pattern in compile_patterns(config.get("part_patterns", [])):
        match = pattern.match(value)
        if match:
            part = match.group(1) if match.groups() else value
            return 1, value.title() if value.isupper() else value, f"part_{part}"

    for pattern in compile_patterns(config.get("section_patterns", [])):
        match = pattern.match(value)
        if match:
            section = match.group(1) if match.groups() else None
            return 2, value, section

    for pattern in compile_patterns(config.get("clause_patterns", [])):
        match = pattern.match(value)
        if match:
            return 3 + match.group(1).count("."), value, match.group(1)

    match = SECTION_ID_PATTERN.match(value)
    if match:
        return 3 + match.group(1).count("."), value, match.group(1)

    return None


def classify_pending_text(lines: list[str]) -> str:
    joined = " ".join(lines).strip()
    if not joined:
        return "paragraph"
    if joined.startswith(("•", "-", "–")):
        return "list_item"
    if re.match(
        r"^(?:\d+\.|[a-z]\)|[A-Z]\)|[ivxlcdm]+\))\s+",
        joined,
        re.IGNORECASE,
    ):
        return "list_item"
    if joined.lower().startswith("table "):
        return "table"
    return "paragraph"


def normalise_pdf_document(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Normalise non-tariff PDFs with generic, conservative heading rules."""
    blocks: list[dict[str, Any]] = []
    ordinal = 0
    active_headings: dict[int, str] = {}
    repeated_patterns = compile_patterns(config.get("repeated_line_patterns", []))
    skip_pages = set(config.get("skip_pdf_pages", []))
    boilerplate_lines_removed = 0
    flagged = 0

    for page in document.get("pages", []):
        page_number = page["page_number"]
        if page_number in skip_pages:
            continue

        raw_lines = page.get("text", "").splitlines()
        printed_page = detect_printed_page_label(raw_lines)
        cleaned_lines: list[str] = []
        for raw_line in raw_lines:
            line = normalise_whitespace(raw_line)
            if not line:
                cleaned_lines.append("")
                continue
            if line_matches_any(line, repeated_patterns):
                boilerplate_lines_removed += 1
                continue
            cleaned_lines.append(line)

        pending: list[str] = []

        def flush_pending() -> None:
            nonlocal ordinal, flagged
            text = normalise_whitespace(" ".join(pending))
            if not text:
                pending.clear()
                return
            block_flags: list[str] = []
            if not active_headings:
                block_flags.append("no_detected_heading_path")
                flagged += 1
            ordinal += 1
            blocks.append(
                make_block(
                    document=document,
                    ordinal=ordinal,
                    block_type=classify_pending_text(pending),
                    text=text,
                    heading_path=[active_headings[key] for key in sorted(active_headings)],
                    citation={
                        "pdf_page_start": page_number,
                        "pdf_page_end": page_number,
                        "printed_page_start": printed_page,
                        "printed_page_end": printed_page,
                        "section_ids": [
                            item.split(" ", 1)[0]
                            for item in active_headings.values()
                            if re.match(r"^\d+(?:\.\d+)+", item)
                        ],
                    },
                    flags=block_flags,
                )
            )
            pending.clear()

        for line in cleaned_lines:
            if not line:
                flush_pending()
                continue
            if printed_page and line == printed_page:
                continue

            detected = detect_heading(line, config)
            if detected:
                flush_pending()
                level, heading, section_id = detected
                active_headings = {
                    key: value for key, value in active_headings.items() if key < level
                }
                active_headings[level] = heading
                ordinal += 1
                blocks.append(
                    make_block(
                        document=document,
                        ordinal=ordinal,
                        block_type="heading",
                        text=heading,
                        heading_path=[active_headings[key] for key in sorted(active_headings)],
                        citation={
                            "pdf_page_start": page_number,
                            "pdf_page_end": page_number,
                            "printed_page_start": printed_page,
                            "printed_page_end": printed_page,
                            "section_ids": [section_id] if section_id else [],
                        },
                        heading_level=level,
                        heading=heading,
                    )
                )
                continue

            pending.append(line)

        flush_pending()

    return {
        "schema_version": NORMALISATION_SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source_type": "pdf",
        "normalised_at": now_iso(),
        "normalisation_method": "deterministic_pdf_page_and_heading_parser",
        "source": document["source"],
        "blocks": blocks,
        "normalisation_summary": {
            "input_pages": len(document.get("pages", [])),
            "output_blocks": len(blocks),
            "boilerplate_lines_removed": boilerplate_lines_removed,
            "blocks_flagged_for_review": flagged,
        },
    }


def tariff_page_metadata(text: str) -> dict[str, str | None]:
    flattened = normalise_whitespace(text)
    rule_sheet = TARIFF_RULE_SHEET_PATTERN.search(flattened)
    cpuc_sheet = TARIFF_CPUC_SHEET_PATTERN.search(flattened)
    effective_date = TARIFF_EFFECTIVE_DATE_PATTERN.search(flattened)
    advice = TARIFF_ADVICE_PATTERN.search(flattened)
    return {
        "tariff_rule_sheet": rule_sheet.group(1) if rule_sheet else None,
        "tariff_cpuc_sheet": cpuc_sheet.group(1) if cpuc_sheet else None,
        "tariff_effective_date": effective_date.group(1) if effective_date else None,
        "tariff_advice_letter": advice.group(1) if advice else None,
    }


def tariff_citation(
    page_number: int,
    metadata: dict[str, str | None],
    section_ids: list[str],
) -> dict[str, Any]:
    return {
        "pdf_page_start": page_number,
        "pdf_page_end": page_number,
        "printed_page_start": metadata.get("tariff_rule_sheet"),
        "printed_page_end": metadata.get("tariff_rule_sheet"),
        "section_ids": section_ids,
        "tariff_rule_sheet": metadata.get("tariff_rule_sheet"),
        "tariff_cpuc_sheet": metadata.get("tariff_cpuc_sheet"),
        "tariff_effective_date": metadata.get("tariff_effective_date"),
        "tariff_advice_letter": metadata.get("tariff_advice_letter"),
    }


def is_tariff_administrative_line(line: str) -> bool:
    if not line:
        return False
    if re.fullmatch(r"\([A-Z]\)", line):
        return True
    if re.fullmatch(r"\|", line):
        return True
    if re.match(r"^\d+C\d+\s+Resolution\b", line, re.IGNORECASE):
        return True
    return any(
        line.startswith(prefix)
        for prefix in (
            "Southern California Edison",
            "Rosemead, California",
            "Rule 21 Sheet",
            "GENERATING FACILITY INTERCONNECTIONS",
            "(Continued)",
            "(To be inserted by utility)",
            "Advice ",
            "Decision ",
        )
    )


def is_tariff_roman_subheading(line: str) -> bool:
    """Identify short title-like roman entries that serve as tariff subheadings."""
    match = TARIFF_ROMAN_LIST_ITEM_PATTERN.match(line)
    if not match:
        return False

    label = match.group(2).strip()
    return (
        len(label) <= 80
        and label[:1].isupper()
        and not label.endswith((".", ";", ":"))
    )


def detect_tariff_heading(line: str) -> tuple[int, str, str] | None:
    """Recognise the Rule 21 hierarchy and qualifying roman subheadings."""
    value = normalise_whitespace(line)
    if not value or value in {
        "(Continued)",
        "A. TABLE OF CONTENTS",
        "A. TABLE OF CONTENTS (Continued)",
    }:
        return None

    match = TARIFF_APPENDIX_PATTERN.match(value)
    if match:
        appendix_id = match.group(1).upper()
        return 1, f"APPENDIX {appendix_id}", f"appendix_{appendix_id}"

    match = TARIFF_LETTER_SECTION_PATTERN.match(value)
    if match:
        return 1, value, match.group(1)

    match = TARIFF_NUMBERED_HEADING_PATTERN.match(value)
    if match:
        return 2, value, match.group(1)

    match = TARIFF_LETTER_HEADING_PATTERN.match(value)
    if match:
        return 3, value, match.group(1)

    match = TARIFF_ROMAN_LIST_ITEM_PATTERN.match(value)
    if match and is_tariff_roman_subheading(value):
        return 4, value, match.group(1).lower()

    return None


def normalise_sce_rule21_tariff(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Normalise the SCE Rule 21 tariff without changing raw extraction artifacts.

    The tariff uses a lettered-section / numeric / lettered-subsection hierarchy.
    Short title-like roman entries are retained as level-four headings; prose-like
    roman entries are retained as list items. Administrative sheet text is removed
    from normalised evidence blocks but remains available through page citation metadata.
    """
    blocks: list[dict[str, Any]] = []
    ordinal = 0
    active_headings: dict[int, tuple[str, str]] = {}
    skip_pages = set(config.get("skip_pdf_pages", []))
    boilerplate_lines_removed = 0
    skipped_contents_pages = 0
    flagged = 0

    for page in document.get("pages", []):
        page_number = page["page_number"]
        raw_text = page.get("text", "")
        metadata = tariff_page_metadata(raw_text)
        raw_lines = raw_text.splitlines()
        is_contents_page = "A. TABLE OF CONTENTS" in normalise_whitespace(raw_text)

        if page_number in skip_pages or is_contents_page:
            skipped_contents_pages += int(is_contents_page)
            continue

        pending: list[str] = []

        def current_path() -> list[str]:
            return [active_headings[level][1] for level in sorted(active_headings)]

        def current_section_ids() -> list[str]:
            return [active_headings[level][0] for level in sorted(active_headings)]

        def flush_pending() -> None:
            nonlocal ordinal, flagged
            text = normalise_whitespace(" ".join(pending))
            if not text:
                pending.clear()
                return

            block_flags: list[str] = []
            if not active_headings:
                block_flags.append("no_detected_heading_path")
                flagged += 1

            ordinal += 1
            blocks.append(
                make_block(
                    document=document,
                    ordinal=ordinal,
                    block_type=classify_pending_text(pending),
                    text=text,
                    heading_path=current_path(),
                    citation=tariff_citation(
                        page_number,
                        metadata,
                        current_section_ids(),
                    ),
                    flags=block_flags,
                )
            )
            pending.clear()

        for raw_line in raw_lines:
            line = normalise_whitespace(raw_line)
            if not line:
                flush_pending()
                continue

            if is_tariff_administrative_line(line):
                boilerplate_lines_removed += 1
                continue

            # Heading detection must happen before generic roman-list handling.
            # This allows "iv) Special Circumstances" to become a heading while
            # preserving long prose-style entries such as "i) an irrevocable ..."
            # as list items.
            detected = detect_tariff_heading(line)
            if detected:
                flush_pending()
                level, heading, section_id = detected
                active_headings = {
                    existing_level: existing
                    for existing_level, existing in active_headings.items()
                    if existing_level < level
                }
                active_headings[level] = (section_id, heading)
                ordinal += 1
                blocks.append(
                    make_block(
                        document=document,
                        ordinal=ordinal,
                        block_type="heading",
                        text=heading,
                        heading_path=current_path(),
                        citation=tariff_citation(
                            page_number,
                            metadata,
                            current_section_ids(),
                        ),
                        heading_level=level,
                        heading=heading,
                    )
                )
                continue

            if TARIFF_ROMAN_LIST_ITEM_PATTERN.match(line):
                pending.append(line)
                continue

            pending.append(line)

        flush_pending()

    return {
        "schema_version": NORMALISATION_SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source_type": "pdf",
        "normalised_at": now_iso(),
        "normalisation_method": "deterministic_sce_rule21_tariff_parser",
        "source": document["source"],
        "blocks": blocks,
        "normalisation_summary": {
            "input_pages": len(document.get("pages", [])),
            "output_blocks": len(blocks),
            "boilerplate_lines_removed": boilerplate_lines_removed,
            "contents_pages_skipped": skipped_contents_pages,
            "blocks_flagged_for_review": flagged,
        },
    }


def normalise_document(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    document_config = source_config(config, document["document_id"])
    if document["source_type"] == "html":
        return normalise_html_document(document, document_config)
    if document["document_id"] == "sce_rule21_tariff_pdf":
        return normalise_sce_rule21_tariff(document, document_config)
    if document["source_type"] == "pdf":
        return normalise_pdf_document(document, document_config)
    raise ValueError(f"Unsupported source type: {document['source_type']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    args = parse_args()
    manifest_path = resolve_path(args.input_manifest)
    config_path = resolve_path(args.config)
    output_dir = resolve_path(args.output_dir)

    manifest = load_json(manifest_path)
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalisation_manifest: dict[str, Any] = {
        "schema_version": NORMALISATION_SCHEMA_VERSION,
        "normalised_at": now_iso(),
        "input_manifest": str(manifest_path.relative_to(PROJECT_ROOT)),
        "documents": [],
        "failures": [],
        "skipped": [],
    }

    for item in manifest.get("documents", []):
        if item.get("status") != "success":
            continue

        input_path = PROJECT_ROOT / item["output_path"]
        try:
            document = load_json(input_path)
            normalised = normalise_document(document, config)
            output_path = output_dir / f"{document['document_id']}.json"
            output_path.write_text(json.dumps(normalised, indent=2), encoding="utf-8")
            normalisation_manifest["documents"].append(
                {
                    "document_id": document["document_id"],
                    "status": "success",
                    "input_path": str(input_path.relative_to(PROJECT_ROOT)),
                    "output_path": str(output_path.relative_to(PROJECT_ROOT)),
                    "source_hash": document["source"].get("content_hash"),
                    "normalised_at": normalised["normalised_at"],
                    "output_blocks": normalised["normalisation_summary"]["output_blocks"],
                }
            )
            print(f"Normalised: {document['document_id']} -> {output_path}")
        except Exception as error:
            normalisation_manifest["failures"].append(
                {
                    "document_id": item.get("document_id"),
                    "status": "failed",
                    "error": str(error),
                    "failed_at": now_iso(),
                }
            )
            print(f"FAILED: {item.get('document_id')}: {error}")

    manifest_output = output_dir / "normalisation_manifest.json"
    manifest_output.write_text(json.dumps(normalisation_manifest, indent=2), encoding="utf-8")
    print(f"Normalisation manifest: {manifest_output}")

    if normalisation_manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
