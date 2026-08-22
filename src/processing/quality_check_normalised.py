"""Check normalised DER RegCheck documents for traceability and structural quality.

This script reads normalised outputs and writes reports. It does not alter source,
extraction, or normalised content.

Usage:
    uv run python src/processing/quality_check_normalised.py \
      --normalised-dir data/processed/normalised \
      --output-json data/processed/normalised/quality_report.json \
      --output-md data/processed/normalised/quality_report.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NORMALISED_DIR = PROJECT_ROOT / "data" / "processed" / "normalised"
DEFAULT_OUTPUT_JSON = DEFAULT_NORMALISED_DIR / "quality_report.json"
DEFAULT_OUTPUT_MD = DEFAULT_NORMALISED_DIR / "quality_report.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_document(document: dict[str, Any]) -> dict[str, Any]:
    blocks = document.get("blocks", [])
    source_type = document.get("source_type")
    errors: list[str] = []
    warnings: list[str] = []
    block_types = Counter()
    flags = Counter()
    adjacent_duplicates = 0
    short_blocks = 0
    oversized_blocks = 0
    previous_key: tuple[str, str, tuple[str, ...]] | None = None

    for block in blocks:
        block_types[block.get("block_type", "unknown")] += 1
        block_flags = block.get("normalisation_flags", [])
        flags.update(block_flags)

        if not block.get("source_id"):
            errors.append(f"{block.get('block_id')}: missing source_id")
        if not block.get("text"):
            errors.append(f"{block.get('block_id')}: empty text")
        if block.get("is_substantive", True) and not block.get("heading_path"):
            warnings.append(f"{block.get('block_id')}: no heading path")

        text = block.get("text", "")
        word_count = len(text.split())
        if block.get("is_substantive", True) and 0 < word_count < 5:
            short_blocks += 1
        if word_count > 1_200:
            oversized_blocks += 1

        citation = block.get("citation", {})
        if source_type == "pdf" and block.get("is_substantive", True):
            if citation.get("pdf_page_start") is None:
                errors.append(f"{block.get('block_id')}: PDF block missing pdf_page_start")
        if source_type == "html" and block.get("is_substantive", True):
            if not citation.get("heading_path"):
                errors.append(f"{block.get('block_id')}: HTML block missing heading-path citation")

        key = (
            block.get("block_type", "unknown"),
            text,
            tuple(block.get("heading_path", [])),
        )
        if key == previous_key:
            adjacent_duplicates += 1
        previous_key = key

    if not document.get("schema_version"):
        errors.append("document: missing schema_version")
    if not document.get("source", {}).get("content_hash"):
        warnings.append("document: missing source content hash")

    return {
        "document_id": document.get("document_id"),
        "source_type": source_type,
        "block_count": len(blocks),
        "block_types": dict(sorted(block_types.items())),
        "normalisation_flags": dict(sorted(flags.items())),
        "short_substantive_blocks": short_blocks,
        "oversized_blocks_over_1200_words": oversized_blocks,
        "adjacent_duplicate_blocks": adjacent_duplicates,
        "errors": errors,
        "warnings": warnings,
        "status": "fail" if errors else "review" if warnings else "pass",
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Normalisation Quality Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Document | Source type | Blocks | Errors | Warnings | Status |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]

    for item in report["documents"]:
        lines.append(
            "| {document_id} | {source_type} | {block_count} | {errors} | {warnings} | {status} |".format(
                document_id=item["document_id"],
                source_type=item["source_type"],
                block_count=item["block_count"],
                errors=len(item["errors"]),
                warnings=len(item["warnings"]),
                status=item["status"],
            )
        )

    for item in report["documents"]:
        lines.extend(
            [
                "",
                f"## {item['document_id']}",
                "",
                f"- Block types: `{json.dumps(item['block_types'], sort_keys=True)}`",
                f"- Normalisation flags: `{json.dumps(item['normalisation_flags'], sort_keys=True)}`",
                f"- Short substantive blocks: {item['short_substantive_blocks']}",
                f"- Oversized blocks: {item['oversized_blocks_over_1200_words']}",
                f"- Adjacent duplicate blocks: {item['adjacent_duplicate_blocks']}",
            ]
        )
        if item["errors"]:
            lines.extend(["", "### Errors", ""])
            lines.extend(f"- {error}" for error in item["errors"])
        if item["warnings"]:
            lines.extend(["", "### Review warnings", ""])
            lines.extend(f"- {warning}" for warning in item["warnings"])

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalised-dir", type=Path, default=DEFAULT_NORMALISED_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    args = parse_args()
    normalised_dir = resolve_path(args.normalised_dir)
    output_json = resolve_path(args.output_json)
    output_md = resolve_path(args.output_md)

    excluded_names = {
        "normalisation_manifest.json",
        "quality_report.json",
    }
    document_paths = sorted(
        path for path in normalised_dir.glob("*.json") if path.name not in excluded_names
    )
    if not document_paths:
        raise FileNotFoundError(f"No normalised document JSON files found in {normalised_dir}")

    documents = [check_document(load_json(path)) for path in document_paths]
    report = {
        "generated_at": now_iso(),
        "normalised_dir": str(normalised_dir.relative_to(PROJECT_ROOT)),
        "documents": documents,
        "summary": {
            "documents": len(documents),
            "pass": sum(item["status"] == "pass" for item in documents),
            "review": sum(item["status"] == "review" for item in documents),
            "fail": sum(item["status"] == "fail" for item in documents),
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_md.write_text(markdown_report(report), encoding="utf-8")
    print(f"Quality report JSON: {output_json}")
    print(f"Quality report Markdown: {output_md}")

    if report["summary"]["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
