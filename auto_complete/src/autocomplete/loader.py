# src/autocomplete/loader.py
from pathlib import Path
from typing import Iterable, List, Dict
import re
import unicodedata

from .models import Sentence, Corpus
from .config import ENCODING, GLOB_PATTERN

_ws_re = re.compile(r"\s+")

def _strip_punct_and_symbols(s: str) -> str:
    # keep letters/numbers/spaces; drop punctuation & symbols (unicode-aware)
    chars = []
    for ch in s:
        cat = unicodedata.category(ch)
        if ch.isspace() or cat.startswith("L") or cat.startswith("N"):
            chars.append(ch)
        else:
            # replace with space to avoid accidental word joins, collapse later
            chars.append(" ")
    return "".join(chars)

def normalize(text: str) -> str:
    """shared normalization for both loader and search.
    1) casefold, 2) drop punctuation/symbols, 3) collapse spaces, 4) trim
    """
    s = text.casefold()
    s = _strip_punct_and_symbols(s)
    s = _ws_re.sub(" ", s).strip()
    return s

def _iter_txt_files(roots: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for root in roots:
        for p in Path(root).rglob(GLOB_PATTERN):
            if p.is_file():
                files.append(p)
    # stable order for reproducibility
    files.sort()
    return files

def _best_relpath(p: Path, roots: Iterable[str]) -> str:
    # choose the first root that works; fallback to basename
    for root in roots:
        try:
            rel = p.relative_to(Path(root))
            return rel.as_posix()
        except Exception:
            continue
    return p.name

def load_corpus(roots: Iterable[str]) -> Corpus:
    sentences: List[Sentence] = []
    file_prefix_sums: Dict[str, List[int]] = {}

    next_id = 0
    for p in _iter_txt_files(roots):
        rel = _best_relpath(p, roots)

        cumul: List[int] = []
        total = 0
        with p.open("r", encoding=ENCODING, errors="ignore") as f:
            for line_no, raw in enumerate(f, start=1):
                # keep exactly as read (raw includes newline except possibly last line)
                original = raw.rstrip("\n\r")
                normalized = normalize(original)

                sentences.append(Sentence(
                    id=next_id,
                    path=rel,
                    line_no=line_no,
                    original=original,
                    normalized=normalized,
                ))
                next_id += 1

                total += len(raw)     # counts characters including EOL as present
                cumul.append(total)

        file_prefix_sums[rel] = cumul

    return Corpus(sentences=sentences, file_prefix_sums=file_prefix_sums)
