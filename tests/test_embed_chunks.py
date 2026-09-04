from __future__ import annotations

import math
import unittest

import torch
from transformers import AutoModel, AutoTokenizer

from src.processing.embed_chunks import embed_batch


MODEL_ID = "nomic-ai/nomic-embed-text-v1.5"
REVISION = "e9b6763023c676ca8431644204f50c2b100d9aab"


class EmbedChunksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.device = "cuda" if torch.cuda.is_available() else "cpu"

        cls.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            revision=REVISION,
            trust_remote_code=True,
        )

        cls.model = AutoModel.from_pretrained(
            MODEL_ID,
            revision=REVISION,
            trust_remote_code=True,
        ).to(cls.device)

        cls.model.eval()

    def test_embed_batch_returns_l2_normalized_vectors(self) -> None:
        vectors = embed_batch(
            texts=[
                "title: Test | text: Smart inverter reactive power requirements.",
                "title: Test | text: Interconnection application process.",
            ],
            model=self.model,
            tokenizer=self.tokenizer,
            prefix="search_document: ",
            device=self.device,
        )

        self.assertEqual(len(vectors), 2)

        for vector in vectors:
            self.assertEqual(len(vector), 768)

            norm = math.sqrt(sum(value * value for value in vector))

            self.assertTrue(
                math.isclose(
                    norm,
                    1.0,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                ),
                msg=f"Expected L2 norm close to 1.0, got {norm}",
            )


if __name__ == "__main__":
    unittest.main()