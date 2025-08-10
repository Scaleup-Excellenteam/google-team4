from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple, Iterator
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

__all__ = ["fast_walk", "parallel_read"]

DEFAULT_EXCLUDES = {".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "__pycache__"}

def fast_walk(
    root: str | Path,
    include_exts: Optional[Set[str]] = None,
    exclude_dirs: Optional[Set[str]] = None
) -> List[str]:
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(root)

    include_exts = {e.lower() for e in include_exts} if include_exts else None
    exclude_dirs = {d.lower() for d in (exclude_dirs or DEFAULT_EXCLUDES)}

    out: List[str] = []
    stack = [root]

    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    name = entry.name
                    if entry.is_dir(follow_symlinks=False):
                        if name.lower() in exclude_dirs:
                            continue
                        stack.append(Path(cur, name))
                    elif entry.is_file(follow_symlinks=False):
                        if include_exts is not None:
                            if Path(name).suffix.lower() not in include_exts:
                                continue
                        out.append(str(Path(cur, name)))
        except PermissionError:
            continue
    return out

def _read_text(path: str) -> Tuple[str, str]:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")
    return path, text

def parallel_read(
    root: str | Path,
    mode: str = "threads",
    workers: Optional[int] = None,
    exts: Optional[Iterable[str]] = None,
    exclude_dirs: Optional[Iterable[str]] = None
) -> Iterator[Tuple[str, str]]:
    if workers is None:
        cpu = os.cpu_count() or 4
        workers = cpu * 2 if mode == "threads" else cpu

    include_exts: Optional[Set[str]] = None
    if exts:
        include_exts = {e if str(e).startswith(".") else "." + str(e) for e in exts}

    files = fast_walk(root, include_exts=include_exts, exclude_dirs=set(exclude_dirs or []))

    exec_cls = ThreadPoolExecutor if mode == "threads" else ProcessPoolExecutor
    chunksize = 64 if mode == "threads" else max(1, len(files) // (workers * 8) or 1)

    with exec_cls(max_workers=workers) as ex:
        for path, text in ex.map(_read_text, files, chunksize=chunksize):
            yield path, text
