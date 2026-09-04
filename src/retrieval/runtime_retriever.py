"""End-to-end database-backed hybrid retrieval for DER RegCheck."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
import yaml
from transformers import AutoModel, AutoTokenizer

from src.database.db_connection import get_connection
from src.retrieval.rerank import Reranker
from src.retrieval.retrieve import Retriever


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class RuntimeRetriever:
    """Embed a question, retrieve database candidates, and rerank them."""

    def __init__(
        self,
        embedding_config_path: Path | None = None,
        retrieval_config_path: Path | None = None,
    ) -> None:
        embedding_config_path = (
            embedding_config_path
            or ROOT / "config" / "embedding.yaml"
        )

        retrieval_config_path = (
            retrieval_config_path
            or ROOT / "config" / "retrieval.yaml"
        )

        embedding_config = load_yaml(embedding_config_path)["embedding"]
        retrieval_config = load_yaml(retrieval_config_path)

        self.model_id = embedding_config["model_id"]
        self.model_revision = embedding_config["revision"]
        self.query_prefix = embedding_config["prefix_query"]

        self.alpha = float(retrieval_config["hybrid_alpha"])

        reranking_config = retrieval_config["reranking"]
        self.candidate_limit = int(reranking_config["candidate_limit"])
        self.rerank_top_k = int(reranking_config["top_k"])
        self.max_tokens = int(reranking_config["max_tokens"])
        self.batch_size = int(reranking_config.get("batch_size", 16))

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            trust_remote_code=True,
        )

        self.embedding_model = AutoModel.from_pretrained(
            self.model_id,
            revision=self.model_revision,
            trust_remote_code=True,
        ).to(self.device)

        self.embedding_model.eval()

        self.reranker = Reranker()

    def embed_query(self, query: str) -> list[float]:
        """Create a normalized Nomic query embedding."""
        cleaned_query = query.strip()

        if not cleaned_query:
            raise ValueError("query must not be empty.")

        encoded = self.tokenizer(
            f"{self.query_prefix}{cleaned_query}",
            padding=True,
            truncation=True,
            max_length=8192,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            outputs = self.embedding_model(**encoded)

        pooled_embedding = outputs.last_hidden_state[:, 0, :]

        normalized_embedding = F.normalize(
            pooled_embedding,
            p=2,
            dim=1,
        )

        return normalized_embedding.cpu().tolist()[0]

    def retrieve(
        self,
        question: str,
        final_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the final reranked chunks for one user question."""
        if final_k <= 0:
            raise ValueError("final_k must be positive.")

        query_embedding = self.embed_query(question)

        with get_connection() as conn:
            database_retriever = Retriever(conn)

            candidates = database_retriever.search_hybrid(
                query=question,
                query_embedding=query_embedding,
                top_k=self.candidate_limit,
                alpha=self.alpha,
            )

        return self.reranker.rerank(
            query=question,
            chunks=candidates,
            top_k=final_k,
            candidate_limit=self.candidate_limit,
            max_tokens=self.max_tokens,
            batch_size=self.batch_size,
        )


_runtime_retriever: RuntimeRetriever | None = None


def get_runtime_retriever() -> RuntimeRetriever:
    """Return a lazily created, process-wide RuntimeRetriever."""
    global _runtime_retriever

    if _runtime_retriever is None:
        _runtime_retriever = RuntimeRetriever()

    return _runtime_retriever