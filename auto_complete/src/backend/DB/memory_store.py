# backend/DB/memory_store.py
from __future__ import annotations
from typing import Dict, Iterable, Iterator, Optional
from .api import CorpusStore
from ..models import Sentence, Corpus

class MemoryStore(CorpusStore):
    """Simple in-memory CRUD (useful for tests or ephemeral runs)."""
    def __init__(self, corpus: Optional[Corpus]=None) -> None:
        self._rows: Dict[int, Sentence] = {}
        if corpus:
            for s in corpus.sentences:
                self._rows[int(s.id)] = s

    # C
    def create(self, s: Sentence) -> None:
        self._rows[int(s.id)] = s

    def bulk_create(self, items: Iterable[Sentence]) -> int:
        n = 0
        for s in items:
            self._rows[int(s.id)] = s; n += 1
        return n

    # R
    def read(self, sid: int) -> Sentence:
        try:
            return self._rows[int(sid)]
        except KeyError:
            raise KeyError(sid)

    def read_many(self, ids: Iterable[int]) -> Iterator[Sentence]:
        for sid in ids:
            s = self._rows.get(int(sid))
            if s is not None:
                yield s

    def count(self) -> int:
        return len(self._rows)

    # U
    def update(
        self,
        sid: int,
        *,
        path: Optional[str]=None,
        line_no: Optional[int]=None,
        original: Optional[str]=None,
        normalized: Optional[str]=None,
        norm_to_orig: Optional[list[int]]=None,
    ) -> None:
        s = self.read(sid)
        self._rows[sid] = Sentence(
            id=s.id,
            path=path if path is not None else s.path,
            line_no=int(line_no) if line_no is not None else s.line_no,
            original=original if original is not None else s.original,
            normalized=normalized if normalized is not None else s.normalized,
            norm_to_orig=norm_to_orig if norm_to_orig is not None else s.norm_to_orig,
        )

    # D
    def delete(self, sid: int) -> None:
        self._rows.pop(int(sid), None)

    def close(self) -> None:
        self._rows.clear()
