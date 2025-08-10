from __future__ import annotations
from typing import Iterator, Tuple
import unicodedata

from .config import DATA_ROOT, INCLUDE_EXTS, WORKERS, EXCLUDE_DIRS, READ_MODE
from .fast_dir_ingest import parallel_read

def normalize(s: str) -> str:
    
    s = s.casefold()
    out_chars = []
    prev_space = False
    for ch in s:
        if ch.isspace():
            if not prev_space:
                out_chars.append(" ")
            prev_space = True
            continue
        if unicodedata.category(ch).startswith(("P", "S")):
            # skip punctuation/symbols
            continue
        out_chars.append(ch)
        prev_space = False
    return "".join(out_chars).strip()

def iter_documents() -> Iterator[Tuple[str, str]]:
    """
    Yield (path, text) for all files under DATA_ROOT, fast & parallel.
    """
    yield from parallel_read(
        root=DATA_ROOT,
        mode=READ_MODE,
        workers=WORKERS,
        exts=INCLUDE_EXTS,
        exclude_dirs=EXCLUDE_DIRS,
    )
