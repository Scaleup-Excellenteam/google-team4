# backend/DB/api.py
from __future__ import annotations
import os
from typing import Protocol, Iterable, Iterator, Optional

from ..models import Sentence, Corpus
from .corpusdb import CorpusDB
from .sqlite_store import SQLiteStore

_MAGIC = b"CDB1"


class CorpusStore(Protocol):
    # Create
    def create(self, s: Sentence) -> None: ...
    def bulk_create(self, items: Iterable[Sentence]) -> int: ...
    # Read
    def read(self, sid: int) -> Sentence: ...
    def read_many(self, ids: Iterable[int]) -> Iterator[Sentence]: ...
    def count(self) -> int: ...
    # Update
    def update(
        self,
        sid: int,
        *,
        path: Optional[str] = None,
        line_no: Optional[int] = None,
        original: Optional[str] = None,
        normalized: Optional[str] = None,
        norm_to_orig: Optional[list[int]] = None,
    ) -> None: ...
    # Delete
    def delete(self, sid: int) -> None: ...
    # lifecycle
    def close(self) -> None: ...


def _is_valid_cdb(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == _MAGIC
    except FileNotFoundError:
        return False


def make_store(dsn: str, *, corpus: Optional[Corpus] = None) -> CorpusStore:
    """
    Factory:
      - sqlite:///path -> SQLiteStore (יקבל קובץ CDB; נבנה אוטומטית אם חסר/לא תקין)
      - memory://      -> MemoryStore (אם יש corpus נזריק אותו)
    """
    if dsn.startswith("sqlite:///"):
        path = dsn.removeprefix("sqlite:///")

        # אם הקובץ לא קיים או לא CDB חוקי — נבנה אותו מה-corpus (כשמריצים --build זה קיים)
        if not _is_valid_cdb(path):
            if corpus is None:
                raise RuntimeError(
                    f"{path} is not a valid CDB and no corpus provided. "
                    f"Run a build that supplies a corpus or point --db to an existing .cdb/.sqlite (CDB format)."
                )
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            CorpusDB.build_from_corpus(corpus, path)

        # Lazy import למניעת circular import
        return SQLiteStore(path)

    if dsn.startswith("memory://"):
        from .memory_store import MemoryStore
        return MemoryStore(corpus=corpus)

    raise ValueError(f"Unsupported store DSN: {dsn}")
