from __future__ import annotations
import io
import mmap
import os
import struct
from typing import Iterable, Tuple, Set, List

_MAGIC = b"ACX1"
_U32 = struct.Struct("<I")  # little-endian uint32

class ACXWriter:
    """
    Write a memory-mappable k-gram index file.
    Layout:
      0..3   : 'ACX1'
      4..7   : K (uint32)
      8..11  : N (uint32) number of keys
      Then N entries:
         [len:u1][key:len bytes][off:u32][cnt:u32]
      Then postings region:
         concatenated uint32 sentence IDs (little-endian)
    """
    def __init__(self, k: int) -> None:
        self.k = k

    def save(self, path: str, items: Iterable[Tuple[str, Iterable[int]]]) -> None:
        keys: List[bytes] = []
        lens: List[int] = []
        offs: List[int] = []
        cnts: List[int] = []
        postings: List[int] = []

        off = 0
        for key, ids in items:
            kb = key.encode("utf-8")
            if len(kb) > 255:
                raise ValueError("K-gram key too long for ACX (max 255 bytes)")
            id_list = list(ids)
            keys.append(kb)
            lens.append(len(kb))
            offs.append(off)
            cnts.append(len(id_list))
            postings.extend(id_list)
            off += len(id_list)

        with open(path, "wb") as f:
            f.write(_MAGIC)
            f.write(_U32.pack(self.k))
            f.write(_U32.pack(len(keys)))
            for kb, ln, off, cnt in zip(keys, lens, offs, cnts):
                f.write(bytes([ln]))
                f.write(kb)
                f.write(_U32.pack(off))
                f.write(_U32.pack(cnt))
            buf = io.BytesIO()
            for sid in postings:
                buf.write(_U32.pack(sid))
            f.write(buf.getvalue())

class ACXIndex:
    """
    Read-only memory-mapped index. get(key)->Set[int]
    Keeps only keys/metadata in Python; postings are read via mmap slice.
    """
    def __init__(self, path: str):
        self._path = os.path.abspath(path)
        self._fd = open(self._path, "rb")
        self._mm = mmap.mmap(self._fd.fileno(), length=0, access=mmap.ACCESS_READ)
        self.k = 0
        self.keys: List[str] = []
        self._offs: List[int] = []
        self._cnts: List[int] = []
        self._postings_base = 0
        self._parse_header()

    def _parse_header(self) -> None:
        mm = self._mm
        if mm.read(4) != _MAGIC:
            raise ValueError("Invalid ACX file")
        self.k = _U32.unpack(mm.read(4))[0]
        n = _U32.unpack(mm.read(4))[0]
        keys: List[str] = []
        offs: List[int] = []
        cnts: List[int] = []
        for _ in range(n):
            ln = mm.read(1)[0]
            kb = mm.read(ln)
            keys.append(kb.decode("utf-8"))
            off = _U32.unpack(mm.read(4))[0]
            cnt = _U32.unpack(mm.read(4))[0]
            offs.append(off)
            cnts.append(cnt)
        self.keys = keys
        self._offs = offs
        self._cnts = cnts
        self._postings_base = mm.tell()

    def get(self, key: str) -> Set[int]:
        import bisect
        i = bisect.bisect_left(self.keys, key)
        if i == len(self.keys) or self.keys[i] != key:
            return set()
        off = self._offs[i]
        cnt = self._cnts[i]
        if cnt == 0:
            return set()
        start = self._postings_base + off * 4
        end = start + cnt * 4
        mv = memoryview(self._mm)[start:end]
        return set(int.from_bytes(mv[i:i+4], "little") for i in range(0, len(mv), 4))

    def close(self) -> None:
        try:
            self._mm.close()
        finally:
            self._fd.close()
