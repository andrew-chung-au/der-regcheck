"""Create deterministic, evidence-preserving chunks from normalised DER RegCheck blocks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "1.0"
ROOT = Path(__file__).resolve().parents[2]
TOKEN_RE = re.compile(r"\w+(?:['’-]\w+)?|[^\w\s]", re.UNICODE)
EXCLUDED_INPUTS = {"normalisation_manifest.json", "quality_report.json"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def substantive(block: dict[str, Any]) -> bool:
    return block.get("is_substantive", True) and bool(block.get("text", "").strip())


def policy(config: dict[str, Any], source_id: str) -> dict[str, Any]:
    try:
        return config["source_policy"][source_id]
    except KeyError as error:
        raise ValueError(f"Missing source policy for {source_id}") from error


def merge_citations(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    citations = [block.get("citation", {}) for block in blocks]
    first, last = citations[0], citations[-1]
    merged = dict(first)
    for key in ("pdf_page_end", "printed_page_end"):
        merged[key] = last.get(key, first.get(key))
    section_ids: list[str] = []
    for citation in citations:
        for section_id in citation.get("section_ids", []):
            if section_id not in section_ids:
                section_ids.append(section_id)
    merged["section_ids"] = section_ids
    return merged


def split_group(blocks: list[dict[str, Any]], hard: int, overlap: int) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    for block in blocks:
        size = tokens(block["text"])
        if current and current_tokens + size > hard:
            groups.append(current)
            carry: list[dict[str, Any]] = []
            carry_tokens = 0
            for prior in reversed(current):
                prior_tokens = tokens(prior["text"])
                if carry and carry_tokens + prior_tokens > overlap:
                    break
                carry.insert(0, prior)
                carry_tokens += prior_tokens
            current = carry
            current_tokens = carry_tokens

        current.append(block)
        current_tokens += size

    if current:
        groups.append(current)
    return groups


def structural_groups(blocks: list[dict[str, Any]], config: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Keep nested headings with their first substantive descendant.

    A parent heading must not become a standalone orphan chunk merely because its
    immediately following block is a nested heading with a longer heading path.
    """
    soft = config["chunking"]["soft_max_tokens"]
    hard = config["chunking"]["hard_max_tokens"]
    overlap = config["chunking"]["oversized_overlap_tokens"]
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0

    for block in blocks:
        size = tokens(block["text"])
        current_path = current[0].get("heading_path", []) if current else []
        current_has_only_headings = current and all(
            item["block_type"] == "heading" for item in current
        )
        starts_new_sibling_section = (
            current
            and block["block_type"] == "heading"
            and block.get("heading_path", []) != current_path
            and not current_has_only_headings
        )

        if starts_new_sibling_section or (current and current_tokens + size > soft):
            groups.append(current)
            current, current_tokens = [], 0

        if block["block_type"] == "table":
            if current and current_tokens + size <= hard:
                current.append(block)
                groups.append(current)
                current, current_tokens = [], 0
            else:
                if current:
                    groups.append(current)
                groups.append([block])
                current, current_tokens = [], 0
            continue

        current.append(block)
        current_tokens += size

    if current:
        groups.append(current)

    output: list[list[dict[str, Any]]] = []
    for group in groups:
        if sum(tokens(block["text"]) for block in group) > hard:
            output.extend(split_group(group, hard, overlap))
        else:
            output.append(group)
    return output


def chunk_heading_path(blocks: list[dict[str, Any]]) -> list[str]:
    """Use the first substantive non-heading block's path for the chunk locator."""
    for block in blocks:
        if block["block_type"] != "heading":
            return block.get("heading_path", [])
    return blocks[-1].get("heading_path", [])


def make_chunk(
    document: dict[str, Any],
    source_policy: dict[str, Any],
    blocks: list[dict[str, Any]],
    ordinal: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    evidence = "\n\n".join(block["text"].strip() for block in blocks)
    heading_path = chunk_heading_path(blocks)
    heading = " > ".join(heading_path)
    embedding_body = (
        f"Section: {heading}\n\n{evidence}"
        if heading and config["chunking"]["prepend_heading_path_to_embedding_text"]
        else evidence
    )
    title = document["source"].get("title", document["document_id"])
    chunk_id = f"{document['document_id']}:c{ordinal:04d}"
    estimated = tokens(evidence)
    flags = []
    if estimated > config["chunking"]["hard_max_tokens"]:
        flags.append("single_block_exceeds_hard_limit")

    return {
        "chunk_id": chunk_id,
        "schema_version": SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source_id": document["source"]["id"],
        "source_hash": document["source"].get("content_hash"),
        "chunk_ordinal": ordinal,
        "block_ids": [block["block_id"] for block in blocks],
        "block_types": [block["block_type"] for block in blocks],
        "heading_path": heading_path,
        "evidence_text": evidence,
        "evidence_text_sha256": "sha256:" + hashlib.sha256(evidence.encode()).hexdigest(),
        "embedding_text": f"title: {title} | text: {embedding_body}",
        "estimated_evidence_tokens": estimated,
        "estimated_embedding_tokens": tokens(f"title: {title} | text: {embedding_body}"),
        "citation": merge_citations(blocks),
        "source_policy": source_policy,
        "previous_chunk_id": None,
        "next_chunk_id": None,
        "chunking_flags": flags,
    }


def chunk_document(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    source_policy = policy(config, document["source"]["id"])
    blocks = [block for block in document.get("blocks", []) if substantive(block)]
    groups = structural_groups(blocks, config)
    chunks = [
        make_chunk(document, source_policy, group, index, config)
        for index, group in enumerate(groups, 1)
    ]

    for index, chunk in enumerate(chunks):
        if index:
            chunk["previous_chunk_id"] = chunks[index - 1]["chunk_id"]
        if index < len(chunks) - 1:
            chunk["next_chunk_id"] = chunks[index + 1]["chunk_id"]

    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source": document["source"],
        "chunked_at": now_iso(),
        "chunking_method": "structural_block_assembly_v1",
        "source_policy": source_policy,
        "chunks": chunks,
        "chunking_summary": {
            "input_blocks": len(blocks),
            "output_chunks": len(chunks),
            "historical_only": source_policy["retrieval_tier"] == "historical_only",
            "chunks_over_hard_limit": sum(bool(chunk["chunking_flags"]) for chunk in chunks),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/processed/normalised")
    parser.add_argument("--config", type=Path, default=ROOT / "config/chunking.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/chunks")
    args = parser.parse_args()
    input_dir, config_path, output_dir = map(
        absolute,
        (args.input_dir, args.config, args.output_dir),
    )
    config = load_yaml(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "chunked_at": now_iso(),
        "embedding": config["embedding"],
        "documents": [],
        "failures": [],
    }

    for path in sorted(item for item in input_dir.glob("*.json") if item.name not in EXCLUDED_INPUTS):
        try:
            document = load_json(path)
            output = chunk_document(document, config)
            destination = output_dir / path.name
            destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
            manifest["documents"].append(
                {
                    "document_id": document["document_id"],
                    "status": "success",
                    "output_path": str(destination.relative_to(ROOT)),
                    "output_chunks": output["chunking_summary"]["output_chunks"],
                }
            )
            print(f"Chunked: {document['document_id']} -> {destination}")
        except Exception as error:
            manifest["failures"].append(
                {
                    "input_file": path.name,
                    "error": str(error),
                    "failed_at": now_iso(),
                }
            )
            print(f"FAILED: {path.name}: {error}")

    manifest_path = output_dir / "chunk_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Chunk manifest: {manifest_path}")
    if manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
