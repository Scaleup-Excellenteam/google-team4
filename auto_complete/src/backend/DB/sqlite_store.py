# backend/DB/sqlite_store.py
from __future__ import annotations
import sqlite3
from array import array
from typing import Iterable, Iterator, Optional
from .api import CorpusStore
from .corpusdb import CorpusDB  # re-use your existing reader/iterator
from ..models import Sentence

# copy of the schema (kept in sync with corpusdb.py)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sentences (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  original TEXT NOT NULL,
  normalized TEXT NOT NULL,
  mapping BLOB NOT NULL
);
"""

class SQLiteStore(CorpusStore):
    """CRUD wrapper that composes your existing CorpusDB reader."""
    def __init__(self, db_path: str) -> None:
        self.db = CorpusDB(db_path)               # provides count/get/iter + connection
        self.conn: sqlite3.Connection = self.db.conn
        self.conn.executescript(_SCHEMA)

    # ---- Create ----
    def create(self, s: Sentence) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO sentences(id, path, line_no, original, normalized, mapping) "
            "VALUES (?,?,?,?,?,?)",
            (
                s.id, s.path, s.line_no, s.original, s.normalized,
                array("I", s.norm_to_orig).tobytes(),
            ),
        )
        self.conn.commit()

    def bulk_create(self, items: Iterable[Sentence]) -> int:
        rows = [
            (s.id, s.path, s.line_no, s.original, s.normalized,
             array("I", s.norm_to_orig).tobytes())
            for s in items
        ]
        self.conn.executemany(
            "INSERT OR REPLACE INTO sentences(id, path, line_no, original, normalized, mapping) "
            "VALUES (?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()
        return len(rows)

    # ---- Read ----
    def read(self, sid: int) -> Sentence:
        return self.db.get_sentence(sid)

    def read_many(self, ids: Iterable[int]) -> Iterator[Sentence]:
        return self.db.iter_sentences(ids)

    def count(self) -> int:
        return self.db.count()

    # ---- Update ----
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
        sets, vals = [], []
        if path is not None:        sets += ["path=?"];        vals += [path]
        if line_no is not None:     sets += ["line_no=?"];     vals += [int(line_no)]
        if original is not None:    sets += ["original=?"];    vals += [original]
        if normalized is not None:  sets += ["normalized=?"];  vals += [normalized]
        if norm_to_orig is not None:
            sets += ["mapping=?"];  vals += [array("I", norm_to_orig).tobytes()]
        if not sets:
            return
        vals += [sid]
        self.conn.execute(f"UPDATE sentences SET {', '.join(sets)} WHERE id=?", vals)
        self.conn.commit()

    # ---- Delete ----
    def delete(self, sid: int) -> None:
        self.conn.execute("DELETE FROM sentences WHERE id=?", (sid,))
        self.conn.commit()

    # ---- lifecycle ----
    def close(self) -> None:
        self.db.close()
