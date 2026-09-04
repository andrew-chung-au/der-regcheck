"""Simple timing context manager for performance profiling."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def timed(label: str) -> Iterator[None]:
    """Measure and print elapsed time for a code block."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"[TIMING] {label}: {elapsed:.2f}s")