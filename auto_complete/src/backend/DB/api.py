# backend/DB/api.py
from __future__ import annotations
from typing import Protocol, Iterable, Iterator, Optional
from ..models import Sentence, Corpus

class CorpusStore(Protocol):
    """Abstract CRUD interface for sentence storage."""
    # C (Create)
    def create(self, s: Sentence) -> None: ...
    def bulk_create(self, items: Iterable[Sentence]) -> int: ...

    # R (Read)
    def read(self, sid: int) -> Sentence: ...
    def read_many(self, ids: Iterable[int]) -> Iterator[Sentence]: ...
    def count(self) -> int: ...

    # U (Update)
    def update(
        self,
        sid: int,
        *,
        path: Optional[str]=None,
        line_no: Optional[int]=None,
        original: Optional[str]=None,
        normalized: Optional[str]=None,
        norm_to_orig: Optional[list[int]]=None,
    ) -> None: ...

    # D (Delete)
    def delete(self, sid: int) -> None: ...

    # lifecycle
    def close(self) -> None: ...

# ---- Simple factory (swap by DSN-like string) ----

def make_store(dsn: str, *, corpus: Optional[Corpus]=None) -> CorpusStore:
    """
    Examples:
      'sqlite:///path/to/corpus.sqlite'
      'memory://' (requires corpus=Corpus to seed, or starts empty)
    """
    if dsn.startswith("sqlite:///"):
        from .sqlite_store import SQLiteStore
        return SQLiteStore(dsn.removeprefix("sqlite:///"))
    elif dsn.startswith("memory://"):
        from .memory_store import MemoryStore
        return MemoryStore(corpus=corpus)
    raise ValueError(f"Unsupported store DSN: {dsn}")
