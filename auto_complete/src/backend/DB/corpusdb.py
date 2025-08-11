from __future__ import annotations
import io
import mmap
import os
import struct
from array import array
from typing import Iterable, Iterator, Dict, Tuple
from ..models import Sentence, Corpus

# File format:
#   0..3   : b"CDB1"
#   4..7   : M (uint32) = number of records
#   Table  : M entries of (id:uint32, off:uint64) sorted by id
#   Records region at variable offsets:
#       path_len:u16 | path:utf8
#       line_no:u32
#       orig_len:u32 | original:utf8
#       norm_len:u32 | normalized:utf8
#       map_len:u32  | mapping: map_len * u32 (little-endian)

_MAGIC = b"CDB1"
_U16 = struct.Struct("<H")
_U32 = struct.Struct("<I")
_U64 = struct.Struct("<Q")

class CorpusDB:
    """Flat-file backed corpus; loads only header/table on startup; O(1) random access."""
    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        self._fd = open(self.db_path, "rb")
        self._mm = mmap.mmap(self._fd.fileno(), length=0, access=mmap.ACCESS_READ)
        self._idx: Dict[int, int] = {}   # sid -> offset
        self._parse_header()

    @classmethod
    def build_from_corpus(cls, corpus: Corpus, db_path: str) -> "CorpusDB":
        # Write header + placeholder table, then records, then fill table.
        db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        # Collect sentences (id, Sentence), keep stable order by id
        items: list[Tuple[int, Sentence]] = [(int(s.id), s) for s in corpus.sentences]
        items.sort(key=lambda t: t[0])
        M = len(items)

        tmp = f"{db_path}.tmp"
        with open(tmp, "wb") as f:
            f.write(_MAGIC)
            f.write(_U32.pack(M))
            # Placeholder table (M * (id:u32, off:u64))
            table_pos = f.tell()
            f.write(b"\x00" * (M * (4 + 8)))

            # Write records, track offsets
            offsets: list[Tuple[int, int]] = []  # (id, off)
            for sid, s in items:
                off = f.tell()
                _write_record(f, s)
                offsets.append((sid, off))

            # Fill table
            f.seek(table_pos)
            for sid, off in offsets:
                f.write(_U32.pack(sid))
                f.write(_U64.pack(off))
        os.replace(tmp, db_path)
        return cls(db_path)

    def count(self) -> int:
        return len(self._idx)

    def get_sentence(self, sid: int) -> Sentence:
        sid = int(sid)
        try:
            off = self._idx[sid]
        except KeyError:
            raise KeyError(sid)
        return _read_record(self._mm, off)

    def iter_sentences(self, ids: Iterable[int]) -> Iterator[Sentence]:
        for sid in ids:
            sid = int(sid)
            off = self._idx.get(sid)
            if off is not None:
                yield _read_record(self._mm, off)

    # Kept for API parity with the original implementation
    def _fetch_batch(self, ids: list[int]) -> Iterator[Sentence]:
        yield from self.iter_sentences(ids)

    def close(self):
        try:
            self._mm.close()
        finally:
            self._fd.close()

    # ---- internals ----
    def _parse_header(self) -> None:
        mm = self._mm
        if mm.read(4) != _MAGIC:
            raise ValueError("Invalid CDB file")
        M = _U32.unpack(mm.read(4))[0]
        index: Dict[int, int] = {}
        for _ in range(M):
            sid = _U32.unpack(mm.read(4))[0]
            off = _U64.unpack(mm.read(8))[0]
            index[sid] = off
        self._idx = index

def _write_str(f, s: str):
    b = s.encode("utf-8")
    if len(b) > 0xFFFF:
        raise ValueError("path too long")
    f.write(_U16.pack(len(b))); f.write(b)

def _write_bytes32(f, b: bytes):
    f.write(_U32.pack(len(b))); f.write(b)

def _write_record(f, s: Sentence) -> None:
    _write_str(f, s.path)
    f.write(_U32.pack(int(s.line_no)))
    _write_bytes32(f, s.original.encode("utf-8"))
    _write_bytes32(f, s.normalized.encode("utf-8"))
    arr = array("I", s.norm_to_orig)
    f.write(_U32.pack(len(arr)))
    f.write(arr.tobytes())

def _read_str(mm: mmap.mmap, pos: int) -> Tuple[str, int]:
    ln = _U16.unpack_from(mm, pos)[0]; pos += 2
    b = mm[pos:pos+ln]; pos += ln
    return b.decode("utf-8"), pos

def _read_bytes32(mm: mmap.mmap, pos: int) -> Tuple[bytes, int]:
    ln = _U32.unpack_from(mm, pos)[0]; pos += 4
    b = bytes(mm[pos:pos+ln]); pos += ln
    return b, pos

def _read_record(mm: mmap.mmap, off: int) -> Sentence:
    pos = off
    path, pos = _read_str(mm, pos)
    line_no = _U32.unpack_from(mm, pos)[0]; pos += 4
    original_b, pos = _read_bytes32(mm, pos)
    normalized_b, pos = _read_bytes32(mm, pos)
    mlen = _U32.unpack_from(mm, pos)[0]; pos += 4
    mbytes = bytes(mm[pos:pos+(mlen*4)])
    arr = array("I")
    if mbytes:
        arr.frombytes(mbytes)
    return Sentence(
        id=0,  # id is not stored in record; caller knows sid
        path=path,
        line_no=int(line_no),
        original=original_b.decode("utf-8"),
        normalized=normalized_b.decode("utf-8"),
        norm_to_orig=list(arr),
    )

def is_valid_cdb(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == _MAGIC
    except FileNotFoundError:
        return False
