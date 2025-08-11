from __future__ import annotations
import sqlite3
from array import array
from typing import Iterable, Iterator
from .models import Sentence, Corpus

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

class CorpusDB:
    """SQLite-backed corpus; loads rows on demand (fast startup)."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=OFF;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")

    @classmethod
    def build_from_corpus(cls, corpus: Corpus, db_path: str) -> "CorpusDB":
        db = cls(db_path)
        c = db.conn
        c.executescript(_SCHEMA)
        c.execute("DELETE FROM sentences;")
        rows = (
            (s.id, s.path, s.line_no, s.original, s.normalized, array("I", s.norm_to_orig).tobytes())
            for s in corpus.sentences
        )
        c.executemany(
            "INSERT INTO sentences(id, path, line_no, original, normalized, mapping) VALUES (?,?,?,?,?,?)",
            rows,
        )
        c.commit()
        return db

    def count(self) -> int:
        (n,) = self.conn.execute("SELECT COUNT(*) FROM sentences").fetchone()
        return int(n)

    def get_sentence(self, sid: int) -> Sentence:
        row = self.conn.execute(
            "SELECT path, line_no, original, normalized, mapping FROM sentences WHERE id=?",
            (sid,),
        ).fetchone()
        if row is None:
            raise KeyError(sid)
        path, line_no, original, normalized, mapping_blob = row
        arr = array("I")
        if mapping_blob:
            arr.frombytes(mapping_blob)
        return Sentence(id=sid, path=path, line_no=line_no, original=original,
                        normalized=normalized, norm_to_orig=list(arr))

    def iter_sentences(self, ids: Iterable[int]) -> Iterator[Sentence]:
        B = 1000
        buf: list[int] = []
        for sid in ids:
            buf.append(int(sid))
            if len(buf) >= B:
                yield from self._fetch_batch(buf)
                buf.clear()
        if buf:
            yield from self._fetch_batch(buf)

    def _fetch_batch(self, ids: list[int]) -> Iterator[Sentence]:
        q = f"SELECT id, path, line_no, original, normalized, mapping FROM sentences WHERE id IN ({','.join('?'*len(ids))})"
        for sid, path, line_no, original, normalized, mapping_blob in self.conn.execute(q, ids):
            arr = array("I")
            if mapping_blob:
                arr.frombytes(mapping_blob)
            yield Sentence(id=sid, path=path, line_no=line_no, original=original,
                           normalized=normalized, norm_to_orig=list(arr))

    def close(self):
        self.conn.close()
