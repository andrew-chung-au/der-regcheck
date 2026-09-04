"""Embed chunked DER RegCheck documents with Nomic nomic-embed-text-v1.5."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
import yaml
from transformers import AutoModel, AutoTokenizer


SCHEMA_VERSION = "1.0"
ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_INPUTS = {
    "chunk_manifest.json",
    "chunk_quality_report.json",
    "chunk_quality_report.md",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def embed_batch(
    texts: list[str],
    model: AutoModel,
    tokenizer: AutoTokenizer,
    prefix: str,
    device: str,
) -> list[list[float]]:
    """Embed and L2-normalize a batch of texts."""
    prefixed = [prefix + text for text in texts]

    encoded = tokenizer(
        prefixed,
        padding=True,
        truncation=True,
        max_length=8192,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**encoded)

    pooled_embeddings = outputs.last_hidden_state[:, 0, :]

    normalized_embeddings = F.normalize(
        pooled_embeddings,
        p=2,
        dim=1,
    )

    return normalized_embeddings.cpu().tolist()


def embed_document(
    document: dict[str, Any],
    config: dict[str, Any],
    model: AutoModel,
    tokenizer: AutoTokenizer,
    device: str,
) -> dict[str, Any]:
    embed_config = config["embedding"]
    prefix = embed_config["prefix_document"]
    batch_size = embed_config["batch_size"]
    max_retries = embed_config["max_retries"]

    chunks = document["chunks"]
    output_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index in range(0, len(chunks), batch_size):
        batch = chunks[index : index + batch_size]
        texts = [chunk["embedding_text"] for chunk in batch]

        embeddings: list[list[float]] | None = None

        for attempt in range(max_retries):
            try:
                embeddings = embed_batch(
                    texts,
                    model,
                    tokenizer,
                    prefix,
                    device,
                )
                break
            except Exception as error:
                if attempt == max_retries - 1:
                    for chunk in batch:
                        failures.append(
                            {
                                "chunk_id": chunk["chunk_id"],
                                "error": str(error),
                                "failed_at": now_iso(),
                            }
                        )
                    break

                time.sleep(2**attempt)

        if embeddings is None:
            continue

        for chunk, embedding in zip(batch, embeddings, strict=True):
            output_records.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "source_id": chunk["source_id"],
                    "heading_path": chunk["heading_path"],
                    "citation": chunk["citation"],
                    "embedding_text": chunk["embedding_text"],
                    "embedding_text_sha256": chunk.get("evidence_text_sha256"),
                    "embedding": embedding,
                    "estimated_tokens": chunk["estimated_embedding_tokens"],
                    "model_id": embed_config["model_id"],
                    "embedded_at": now_iso(),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document["document_id"],
        "source_id": document["source"]["id"],
        "embedded_at": now_iso(),
        "model_id": embed_config["model_id"],
        "chunks_embedded": len(output_records),
        "chunks_failed": len(failures),
        "records": output_records,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "data/processed/chunks",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/embedding.yaml",
    )
    args = parser.parse_args()

    input_dir = absolute(args.input_dir)
    config_path = absolute(args.config)
    config = load_yaml(config_path)

    embed_config = config["embedding"]
    output_dir = absolute(Path(embed_config["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    print(f"Loading model: {embed_config['model_id']}")
    tokenizer = AutoTokenizer.from_pretrained(
        embed_config["model_id"],
        revision=embed_config["revision"],
        trust_remote_code=True,
    )
    model = AutoModel.from_pretrained(
        embed_config["model_id"],
        revision=embed_config["revision"],
        trust_remote_code=True,
    ).to(device)
    model.eval()

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "embedded_at": now_iso(),
        "model_id": embed_config["model_id"],
        "documents": [],
        "failures": [],
    }

    for path in sorted(
        item
        for item in input_dir.glob("*.json")
        if item.name not in EXCLUDED_INPUTS
    ):
        try:
            document = load_json(path)
            result = embed_document(
                document,
                config,
                model,
                tokenizer,
                device,
            )

            jsonl_path = output_dir / f"{document['document_id']}.jsonl"
            with jsonl_path.open("w", encoding="utf-8") as file:
                for record in result["records"]:
                    file.write(json.dumps(record) + "\n")

            manifest["documents"].append(
                {
                    "document_id": document["document_id"],
                    "output_path": str(jsonl_path.relative_to(ROOT)),
                    "chunks_embedded": result["chunks_embedded"],
                    "chunks_failed": result["chunks_failed"],
                }
            )

            if result["failures"]:
                manifest["failures"].extend(result["failures"])

            print(
                f"Embedded: {document['document_id']} "
                f"({result['chunks_embedded']} chunks, "
                f"{result['chunks_failed']} failures)"
            )

        except Exception as error:
            manifest["failures"].append(
                {
                    "input_file": path.name,
                    "error": str(error),
                    "failed_at": now_iso(),
                }
            )
            print(f"FAILED: {path.name}: {error}")

    manifest_path = output_dir / "embedding_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(f"Embedding manifest: {manifest_path}")

    if manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()