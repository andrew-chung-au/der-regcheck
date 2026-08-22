"""Load existing chunks and embeddings into PostgreSQL database.

This script loads pre-processed chunks and embeddings from JSON/JSONL files
into the PostgreSQL database with pgvector for production RAG retrieval.

Usage:
    uv run python -m src.scripts.load_chunks_to_db

    # Or with custom paths:
    uv run python -m src.scripts.load_chunks_to_db \
        --chunks-dir data/processed/chunks \
        --embeddings-dir data/processed/embeddings
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.database.db_init import init_schema
from src.database.db_chunks import (
    load_chunks_from_json,
    load_embeddings_from_jsonl,
    insert_chunks,
    insert_embeddings,
    get_chunk_count,
    get_embedding_count,
)

ROOT = Path(__file__).resolve().parents[2]  # Goes up to project root


def absolute(path: Path) -> Path:
    """Resolve path relative to project root."""
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    """Main entry point for loading chunks to database."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=ROOT / "data/processed/chunks",
        help="Directory containing chunk JSON files (default: data/processed/chunks)",
    )
    parser.add_argument(
        "--embeddings-dir",
        type=Path,
        default=ROOT / "data/processed/embeddings",
        help="Directory containing embedding JSONL files (default: data/processed/embeddings)",
    )
    args = parser.parse_args()

    chunks_dir = absolute(args.chunks_dir)
    embeddings_dir = absolute(args.embeddings_dir)

    if not chunks_dir.exists():
        parser.error(f"Chunks directory not found: {chunks_dir}")

    if not embeddings_dir.exists():
        parser.error(f"Embeddings directory not found: {embeddings_dir}")

    print("Initialising database schema...")
    init_schema()

    print(f"Loading chunks from {chunks_dir}...")
    chunks = load_chunks_from_json(chunks_dir)
    print(f"Loaded {len(chunks)} chunks")

    print(f"Loading embeddings from {embeddings_dir}...")
    embeddings = load_embeddings_from_jsonl(embeddings_dir)
    print(f"Loaded {len(embeddings)} embeddings")

    if len(chunks) != len(embeddings):
        print(f"WARNING: Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})")

    print("Inserting chunks into database...")
    insert_chunks(chunks)

    print("Inserting embeddings into database...")
    insert_embeddings(embeddings)

    print(f"\n✅ Database migration complete!")
    print(f"  Chunks: {get_chunk_count()}")
    print(f"  Embeddings: {get_embedding_count()}")


if __name__ == "__main__":
    main()