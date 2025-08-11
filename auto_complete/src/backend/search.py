from __future__ import annotations
from typing import Optional, List
from .backend.models import AutoCompleteData, Sentence
from .backend.normalize import normalize_only
from .DataBase.index import KGramIndex
from .backend.config import TOP_K

# Penalty tables by 1-based position
_REPLACE = {1: 5, 2: 4, 3: 3, 4: 2}
_INSERT_DEL = {1: 10, 2: 8, 3: 6, 4: 4}


# Penalty functions for 1-based positions

def _replace_penalty(pos1: int) -> int:
    """Penalty for a replacement at 1-based position pos1."""
    """Returns a negative penalty value."""
    return -(_REPLACE.get(pos1, 1))

def _insdel_penalty(pos1: int) -> int:
    """Penalty for an insertion or deletion at 1-based position pos1."""
    """Returns a negative penalty value."""
    return -(_INSERT_DEL.get(pos1, 2))

def _hamming_one(q: str, t: str) -> Optional[int]:
    """Returns the 1-based position of the differing character, or None if not exactly one."""
    assert len(q) == len(t)
    diff_pos = 0
    for i, (a, b) in enumerate(zip(q, t), start=1):
        if a != b:
            if diff_pos != 0:
                return None
            diff_pos = i
    return diff_pos or None

def _one_added_in_query(q: str, t: str) -> Optional[int]:
    """Returns the 1-based position in query where an extra letter was added, or None if not exactly one."""
    assert len(q) == len(t) + 1
    i = j = 0
    extra_pos: Optional[int] = None
    while i < len(q) and j < len(t):
        if q[i] == t[j]:
            i += 1
            j += 1
        else:
            if extra_pos is not None:
                return None
            extra_pos = i + 1
            i += 1
    if extra_pos is None:
        extra_pos = len(q)
    return extra_pos

def _one_missing_in_query(q: str, t: str) -> Optional[int]:
    """Returns the 1-based position in query where a letter is missing, or None if not exactly one."""
    assert len(q) + 1 == len(t)
    i = j = 0
    gap_pos: Optional[int] = None
    while i < len(q) and j < len(t):
        if q[i] == t[j]:
            i += 1
            j += 1
        else:
            if gap_pos is not None:
                return None
            gap_pos = i + 1
            j += 1
    if gap_pos is None:
        gap_pos = len(q) + 1
    return gap_pos

"""
TODO: 
    - penalties for 2+ edits
"""


# Complete the query against the index, returning top-k results.

def _line_col_from_concat(orig: str, pos: int, base_line: int) -> tuple[int, int]:
    """Convert a char index in a multi-line 'original' block to (line_no, col)."""
    # Count newlines before pos
    # (simple scan is fine here; done only for top-k hits)
    line_add = orig.count("\n", 0, pos)
    last_nl = orig.rfind("\n", 0, pos)
    col = pos if last_nl == -1 else (pos - last_nl - 1)
    return (base_line + line_add, col)

def _choose_better(cur: Optional[tuple], cand: tuple) -> tuple:
    """Choose the better candidate based on score and position."""
    if cur is None:
        return cand
    if cand[0] > cur[0]:
        return cand
    if cand[0] == cur[0] and cand[3] < cur[3]:
        return cand
    return cur

def _best_match_in_sentence(s: Sentence, q_norm: str) -> Optional[tuple[int, int, int]]:
    """Find the best match for q_norm in the sentence s."""
    s_norm = s.normalized
    if not q_norm or not s_norm:
        return None

    # Fast path: exact substring (leftmost)
    idx = s_norm.find(q_norm)
    if idx != -1:
        score = 2 * len(q_norm)
        return (score, idx, len(q_norm))

    best: Optional[tuple[int, int, int, int]] = None  # (score, start, win_len, start_orig_hint)
    qn = len(q_norm)

    # 1-edit: single replacement
    for i in range(0, len(s_norm) - qn + 1):
        win = s_norm[i:i+qn]
        pos = _hamming_one(q_norm, win)
        if pos is None:
            continue
        score = 2 * (qn - 1) + _replace_penalty(pos)
        start_orig = s.norm_to_orig[i] if i < len(s.norm_to_orig) else 0
        best = _choose_better(best, (score, i, qn, start_orig))

    # 1-edit: added letter in query
    if qn >= 2 and len(s_norm) >= qn - 1:
        L = qn - 1
        for i in range(0, len(s_norm) - L + 1):
            win = s_norm[i:i+L]
            pos = _one_added_in_query(q_norm, win)
            if pos is None:
                continue
            score = 2 * L + _insdel_penalty(pos)
            start_orig = s.norm_to_orig[i] if i < len(s.norm_to_orig) else 0
            best = _choose_better(best, (score, i, L, start_orig))

    # 1-edit: missing letter in query
    if len(s_norm) >= qn + 1:
        L = qn + 1
        for i in range(0, len(s_norm) - L + 1):
            win = s_norm[i:i+L]
            pos = _one_missing_in_query(q_norm, win)
            if pos is None:
                continue
            score = 2 * qn + _insdel_penalty(pos)
            start_orig = s.norm_to_orig[i] if i < len(s.norm_to_orig) else 0
            best = _choose_better(best, (score, i, L, start_orig))

    if best is None:
        return None
    return (best[0], best[1], best[2])

def complete_query(query: str, index: KGramIndex, top_k: int = TOP_K) -> List[AutoCompleteData]:
    """Complete the query against the index, returning top-k results."""
    q_norm = normalize_only(query)
    candidates = index.candidate_ids(q_norm)

    results: list[AutoCompleteData] = []
    for s in index.iter_sentences(candidates):
        match = _best_match_in_sentence(s, q_norm) if q_norm else None
        if match is None:
            continue
        score, start_norm, _win_len = match
        # Map normalized start -> original char index (in concatenated original block)
        start_orig_char = 0
        if s.norm_to_orig and 0 <= start_norm < len(s.norm_to_orig):
            start_orig_char = s.norm_to_orig[start_norm]
        # Convert to (line_no, col), allowing multi-line blocks
        line_no, col = _line_col_from_concat(s.original, start_orig_char, s.line_no)

        ac = AutoCompleteData(
            completed_sentence=s.original,
            source_text=s.path,
            offset=(line_no, col),
            score=score
        )
        results.append(ac)

    results.sort(key=lambda a: (-a.score, a.completed_sentence))
    return results[:top_k]
