from __future__ import annotations
import os
from typing import Iterable, List
from .models import Sentence, Corpus
from .normalize import normalize_and_map
from .config import TEXT_UNIT, WINDOW_SIZE, WINDOW_STEP

# Progress logging (set AUTOCOMPLETE_VERBOSE=1 to enable)
VERBOSE = os.environ.get("AUTOCOMPLETE_VERBOSE") == "1"
PROGRESS_EVERY_SENTENCES = 10_000
PROGRESS_EVERY_FILES = 500

def _iter_txt_files(roots: Iterable[str]) -> Iterable[tuple[str, str]]:
    """Yield (root, path) for *.txt files recursively under each root."""
    for root in roots:
        root = os.path.abspath(root)
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith(".txt"):
                    yield root, os.path.join(dirpath, fn)

def _rel_to_any_root(path: str, roots_abs: List[str]) -> str:
    """Return the shortest relative path to any of the given absolute roots."""
    best = path
    for r in roots_abs:
        try:
            rel = os.path.relpath(path, r)
            if len(rel) < len(best):
                best = rel
        except ValueError:
            pass
    return best.replace("\\", "/")

def _yield_line_units(lines: List[str], path_rel: str, start_id: int) -> Iterable[Sentence]:
    sid = start_id
    for i, raw in enumerate(lines):
        original = raw
        normalized, mapping = normalize_and_map(original)
        yield Sentence(
            id=sid,
            path=path_rel,
            line_no=i,
            original=original,
            normalized=normalized,
            norm_to_orig=mapping,
        )
        sid += 1

def _yield_paragraph_units(lines: List[str], path_rel: str, start_id: int) -> Iterable[Sentence]:
    sid = start_id
    block: List[str] = []
    block_start_line = 0
    for i, raw in enumerate(lines):
        if raw.strip() == "":
            if block:
                original = "\n".join(block)
                normalized, mapping = normalize_and_map(original)
                yield Sentence(sid, path_rel, block_start_line, original, normalized, mapping)
                sid += 1
                block = []
            block_start_line = i + 1
        else:
            if not block:
                block_start_line = i
            block.append(raw)
    if block:
        original = "\n".join(block)
        normalized, mapping = normalize_and_map(original)
        yield Sentence(sid, path_rel, block_start_line, original, normalized, mapping)

def _yield_window_units(lines: List[str], path_rel: str, start_id: int, size: int, step: int) -> Iterable[Sentence]:
    sid = start_id
    n = len(lines)
    size = max(1, int(size))
    step = max(1, int(step))
    i = 0
    while i + size <= n:
        block = lines[i:i + size]
        original = "\n".join(block)
        normalized, mapping = normalize_and_map(original)
        yield Sentence(
            id=sid,
            path=path_rel,
            line_no=i,  # first line of the window
            original=original,
            normalized=normalized,
            norm_to_orig=mapping,
        )
        sid += 1
        i += step

def load_corpus(roots: List[str],
                unit: str | None = None,
                window_size: int | None = None,
                window_step: int | None = None) -> Corpus:
    """
    Scan roots for *.txt and build a Corpus.
    unit: "line" (default), "paragraph", or "window".
    For "window": use window_size/window_step (or config defaults).
    """
    sentences: List[Sentence] = []
    next_id = 0
    roots_abs = [os.path.abspath(p) for p in roots]

    unit = (unit or TEXT_UNIT).lower()
    wsize = window_size if window_size is not None else WINDOW_SIZE
    wstep = window_step if window_step is not None else WINDOW_STEP

    file_count = 0
    for _, path in _iter_txt_files(roots):
        rel = _rel_to_any_root(path, roots_abs)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw_lines = [ln.rstrip("\r\n") for ln in f]
        except OSError:
            continue

        if unit == "line":
            gen = _yield_line_units(raw_lines, rel, next_id)
        elif unit == "paragraph":
            gen = _yield_paragraph_units(raw_lines, rel, next_id)
        elif unit == "window":
            gen = _yield_window_units(raw_lines, rel, next_id, wsize, wstep)
        else:
            gen = _yield_line_units(raw_lines, rel, next_id)

        for s in gen:
            sentences.append(s)
            next_id = s.id + 1

        file_count += 1
        if VERBOSE and file_count % PROGRESS_EVERY_FILES == 0:
            print(f"[scanned] files={file_count:,}")
        if VERBOSE and next_id % PROGRESS_EVERY_SENTENCES == 0:
            print(f"[indexed] sentences={next_id:,}")

    if VERBOSE:
        print(f"[done] files={file_count:,} sentences={next_id:,}")
    return Corpus(sentences=sentences)
