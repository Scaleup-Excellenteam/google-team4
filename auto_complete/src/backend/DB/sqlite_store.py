from __future__ import annotations
from typing import Iterable, Iterator, Optional, Dict, Set
from .store_base import CorpusStore           # ← was: from .api import CorpusStore
from .corpusdb import CorpusDB
from ..models import Sentence

class SQLiteStore(CorpusStore):
    def __init__(self, db_path: str) -> None:
        self.db = CorpusDB(db_path)
        self._overlay: Dict[int, Sentence] = {}
        self._deleted: Set[int] = set()
        self._new_ids: Set[int] = set()

    def create(self, s: Sentence) -> None:
        sid = int(s.id)
        self._overlay[sid] = s
        if sid not in self.db._idx:
            self._new_ids.add(sid)
        self._deleted.discard(sid)

    def bulk_create(self, items: Iterable[Sentence]) -> int:
        n = 0
        for s in items:
            self.create(s); n += 1
        return n

    def read(self, sid: int) -> Sentence:
        sid = int(sid)
        if sid in self._deleted:
            raise KeyError(sid)
        s = self._overlay.get(sid)
        if s is not None:
            return s
        base = self.db.get_sentence(sid)
        return Sentence(
            id=sid, path=base.path, line_no=base.line_no,
            original=base.original, normalized=base.normalized,
            norm_to_orig=base.norm_to_orig,
        )

    def read_many(self, ids: Iterable[int]) -> Iterator[Sentence]:
        for sid in ids:
            sid = int(sid)
            if sid in self._deleted:
                continue
            s = self._overlay.get(sid)
            if s is not None:
                yield s; continue
            try:
                base = self.db.get_sentence(sid)
            except KeyError:
                continue
            yield Sentence(
                id=sid, path=base.path, line_no=base.line_no,
                original=base.original, normalized=base.normalized,
                norm_to_orig=base.norm_to_orig,
            )

    def count(self) -> int:
        return self.db.count() - len(self._deleted.intersection(self.db._idx.keys())) + len(self._new_ids)

    def update(self, sid: int, *, path: Optional[str]=None, line_no: Optional[int]=None,
               original: Optional[str]=None, normalized: Optional[str]=None,
               norm_to_orig: Optional[list[int]]=None) -> None:
        cur = self._overlay.get(int(sid))
        if cur is None:
            cur = self.read(int(sid))
        self._overlay[int(sid)] = Sentence(
            id=cur.id,
            path=path if path is not None else cur.path,
            line_no=int(line_no) if line_no is not None else cur.line_no,
            original=original if original is not None else cur.original,
            normalized=normalized if normalized is not None else cur.normalized,
            norm_to_orig=norm_to_orig if norm_to_orig is not None else cur.norm_to_orig,
        )

    def delete(self, sid: int) -> None:
        sid = int(sid)
        self._overlay.pop(sid, None)
        self._deleted.add(sid)
        self._new_ids.discard(sid)

    def close(self) -> None:
        self.db.close()
        self._overlay.clear()
        self._deleted.clear()
        self._new_ids.clear()
