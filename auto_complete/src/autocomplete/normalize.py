from __future__ import annotations
import unicodedata
from typing import List

def _is_word_char(ch: str) -> bool:
    """Letters and digits are kept. Symbols/punctuation are removed from matching."""
    if ch.isalnum():
        return True
    # Spaces handled separately; anything else is punctuation/symbol to drop
    cat = unicodedata.category(ch)
    return False

def normalize_and_map(text: str) -> tuple[str, List[int]]:
    """
    Normalize text for matching and return:
      - normalized string (casefolded, punctuation stripped, spaces collapsed, trimmed)
      - mapping list: normalized index -> original index (in the ORIGINAL string)
    Rules:
      * case-insensitive: compare via .casefold() BUT mapping points to indices of the original string
      * strip punctuation/symbols from matching consideration
      * collapse multiple spaces and trim
    """
    out_chars: list[str] = []
    mapping: List[int] = []

    last_was_space = False
    pending_space_orig_index: int | None = None

    for orig_i, ch in enumerate(text):
        if ch.isspace():
            if pending_space_orig_index is None:
                pending_space_orig_index = orig_i  # first space of this run
            last_was_space = True
            continue

        if _is_word_char(ch):
            # flush one collapsed space before a word char (not at start)
            if last_was_space and out_chars:
                out_chars.append(' ')
                mapping.append(pending_space_orig_index if pending_space_orig_index is not None else orig_i)
            last_was_space = False
            pending_space_orig_index = None

            out_chars.append(ch.casefold())
            mapping.append(orig_i)
        else:
            # punctuation/symbol: drop from matching consideration
            # but do not break space runs
            pass

    # Trim trailing space if any (only if last output is space)
    if out_chars and out_chars[-1] == ' ':
        out_chars.pop()
        mapping.pop()

    return ''.join(out_chars), mapping

def normalize_only(text: str) -> str:
    """Convenience: normalize and return only the normalized string."""
    return normalize_and_map(text)[0]

def kgrams(s: str, k: int) -> set[str]:
    """Return distinct k-grams of s."""
    if k <= 0 or len(s) < k:
        return set()
    return {s[i:i+k] for i in range(len(s) - k + 1)}
