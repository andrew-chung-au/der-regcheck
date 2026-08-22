"""Validate DER RegCheck structural chunk outputs and generate review reports."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {"chunk_manifest.json", "chunk_quality_report.json"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def check_document(document: dict[str, Any], hard_max: int) -> dict[str, Any]:
    chunks = document.get("chunks", [])
    errors: list[str] = []
    warnings: list[str] = []
    flags = Counter()

    for index, chunk in enumerate(chunks):
        chunk_id = chunk.get("chunk_id", f"index:{index}")
        flags.update(chunk.get("chunking_flags", []))
        if not chunk.get("evidence_text"):
            errors.append(f"{chunk_id}: empty evidence_text")
        if not chunk.get("embedding_text"):
            errors.append(f"{chunk_id}: empty embedding_text")
        if not chunk.get("block_ids"):
            errors.append(f"{chunk_id}: no block_ids")
        if chunk.get("source_id") != document.get("source", {}).get("id"):
            errors.append(f"{chunk_id}: source_id does not match document source")
        if not chunk.get("citation"):
            errors.append(f"{chunk_id}: missing citation")
        if chunk.get("estimated_evidence_tokens", 0) > hard_max:
            warnings.append(f"{chunk_id}: exceeds hard token target")
        if index > 0 and chunk.get("previous_chunk_id") != chunks[index - 1].get("chunk_id"):
            errors.append(f"{chunk_id}: invalid previous_chunk_id")
        if index < len(chunks) - 1 and chunk.get("next_chunk_id") != chunks[index + 1].get("chunk_id"):
            errors.append(f"{chunk_id}: invalid next_chunk_id")

    return {
        "document_id": document.get("document_id"),
        "source_id": document.get("source", {}).get("id"),
        "chunk_count": len(chunks),
        "historical_only": document.get("source_policy", {}).get("retrieval_tier") == "historical_only",
        "flags": dict(sorted(flags.items())),
        "errors": errors,
        "warnings": warnings,
        "status": "fail" if errors else "review" if warnings else "pass",
    }


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chunk Quality Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Document | Chunks | Historical only | Errors | Warnings | Status |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for item in report["documents"]:
        lines.append(
            f"| {item['document_id']} | {item['chunk_count']} | {item['historical_only']} | "
            f"{len(item['errors'])} | {len(item['warnings'])} | {item['status']} |"
        )
    for item in report["documents"]:
        lines.extend(["", f"## {item['document_id']}", "", f"- Flags: `{json.dumps(item['flags'])}`"])
        if item["errors"]:
            lines.extend(["", "### Errors", ""])
            lines.extend(f"- {value}" for value in item["errors"])
        if item["warnings"]:
            lines.extend(["", "### Review warnings", ""])
            lines.extend(f"- {value}" for value in item["warnings"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-dir", type=Path, default=ROOT / "data/processed/chunks")
    parser.add_argument("--config", type=Path, default=ROOT / "config/chunking.yaml")
    parser.add_argument("--output-json", type=Path, default=ROOT / "data/processed/chunks/chunk_quality_report.json")
    parser.add_argument("--output-md", type=Path, default=ROOT / "data/processed/chunks/chunk_quality_report.md")
    args = parser.parse_args()
    chunks_dir, config_path, output_json, output_md = map(absolute, (args.chunks_dir, args.config, args.output_json, args.output_md))
    config = load_yaml(config_path)
    paths = sorted(path for path in chunks_dir.glob("*.json") if path.name not in EXCLUDED)
    if not paths:
        raise FileNotFoundError(f"No chunk document JSON files found in {chunks_dir}")

    documents = [check_document(load_json(path), config["chunking"]["hard_max_tokens"]) for path in paths]
    report = {
        "generated_at": now_iso(),
        "documents": documents,
        "summary": {
            "documents": len(documents),
            "pass": sum(item["status"] == "pass" for item in documents),
            "review": sum(item["status"] == "review" for item in documents),
            "fail": sum(item["status"] == "fail" for item in documents),
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output_md.write_text(report_markdown(report), encoding="utf-8")
    print(f"Chunk quality JSON: {output_json}")
    print(f"Chunk quality Markdown: {output_md}")
    if report["summary"]["fail"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
