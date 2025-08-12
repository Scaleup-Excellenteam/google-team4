from __future__ import annotations
from typing import Optional, List
from .models import AutoCompleteData, Sentence
from .normalize import normalize_only
from .DB.index import KGramIndex
from .config import TOP_K
import re
from . import config as CFG

# Normalize and clean the query string for prefix matching

# /* ~~~ keep only letters+spaces, lowercase; drop punctuation ~~~ */
_KEEP = re.compile(r"[a-z ]")

def _clean(s: str) -> str:
    s = s.lower()
    return "".join(ch for ch in s if _KEEP.fullmatch(ch))

def _p_incorrect(pos: int) -> int:
    # 1→-5, 2→-4, 3→-3, 4→-2, else→-1
    return {1:-5, 2:-4, 3:-3, 4:-2}.get(pos, -1)

def _p_addmiss(pos: int) -> int:
    # 1→-10, 2→-8, 3→-6, 4→-4, else→-2
    return {1:-10, 2:-8, 3:-6, 4:-4}.get(pos, -2)

def score_prefix_1edit(query_raw: str, target_raw: str) -> int | None:
    """
    /* ~~~ Returns numeric score, or None if >1 edit is needed.
       Base = 2 * min(len(clean(query)), len(clean(target))).
       - Substitution: at most one differing position
       - Added/Missing: length differs by exactly 1 (penalty by first divergence) ~~~ */
    """
    q = _clean(query_raw)
    t = _clean(target_raw)
    base = 2 * min(len(q), len(t))

    if len(q) == len(t):
        diffs = [i for i,(a,b) in enumerate(zip(q,t), start=1) if a != b]
        if not diffs:
            return base
        return base + _p_incorrect(diffs[0]) if len(diffs) == 1 else None

    if abs(len(q) - len(t)) == 1:
        # find first divergence position (1-based)
        i = 0
        L = min(len(q), len(t))
        while i < L and q[i] == t[i]:
            i += 1
        pos = i + 1  # if divergence at end, this is L+1
        return base + _p_addmiss(pos)

    return None


_WORD = r"\w+"

def _compile_prefix_pattern(query_norm: str) -> re.Pattern:
    """
    /* ~~~ Build pattern matching: all full words of query except last; last as word-prefix.
           Example: "to be" -> r"\bto\s+be\w*" ~~~ */
    """
    toks = re.findall(_WORD, query_norm)
    if not toks:
        return re.compile(r"$a")  # never matches
    if len(toks) == 1:
        pfx = re.escape(toks[0])
        return re.compile(rf"\b{pfx}\w*")
    head = r"\s+".join(re.escape(t) for t in toks[:-1])
    pfx  = re.escape(toks[-1])
    return re.compile(rf"\b{head}\s+{pfx}\w*")



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

# --- ADD THIS: legacy substring fallback used when SEARCH_MODE != "prefix" ---
def complete_query_substring(query: str, index: KGramIndex, top_k: int):
    """
    Legacy substring path.
    Uses the helpers in this file (_best_match_in_sentence, normalize_only)
    so we don't depend on any other module. Safe even if not used when
    SEARCH_MODE='prefix'.
    """
    q_norm = normalize_only(query)
    if not q_norm:
        return []

    # Candidate IDs: prefer an index method if present; otherwise scan all sids.
    if hasattr(index, "candidates_for_substring"):
        cand_ids = index.candidates_for_substring(q_norm)  # type: ignore[attr-defined]
    else:
        cand_ids = range(getattr(index, "_num_sentences", 0))

    rows = []
    for s in index.iter_sentences(cand_ids):
        best = _best_match_in_sentence(s, q_norm)
        if not best:
            continue
        score, start, win_len = best
        rows.append({
            "score": int(score),
            "offset": [int(start), int(start + win_len)],
            "source_text": getattr(s, "path", "") or "",
            "completed_sentence": s.original,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:top_k]
# --- END ADD ---

def complete_query(query: str, index, top_k: int):
    """
    /* ~~~ When SEARCH_MODE='prefix':
           - candidate SIDs come from word-prefix index (with 1-edit expansion on last token)
           - span is found via regex on s.normalized
           - score uses sheet's 1-edit rules
           Otherwise, fall back to your legacy substring path. ~~~ */
    """
    if getattr(CFG, "SEARCH_MODE", "substring") != "prefix":
        # --- legacy flow (unchanged) ---
        return complete_query_substring(query, index, top_k)  # whatever you call it now

    # --- prefix flow ---
    max_terms = getattr(CFG, "MAX_PREFIX_TERMS", 5000)
    max_cands = getattr(CFG, "MAX_PREFIX_CANDIDATES", 20000)

    # pattern over normalized sentence (for offset extraction)
    pat = _compile_prefix_pattern(query)

    # 1) get candidate SIDs
    cand_sids = index.candidates_for_prefix_query(query, max_terms, max_cands)

    rows = []
    for s in index.iter_sentences(cand_sids):
        m = pat.search(s.normalized)
        if not m:
            continue
        start, end = m.span()
        # Extract the matched substring from ORIGINAL text for display/scoring;
        # scoring cleans punctuation anyway, so original is fine.
        target_raw = s.original[start:end]

        sc = score_prefix_1edit(query, target_raw)
        if sc is None:
            continue

        # /* ~~~ Build your row type. Replace with your project's data class if needed. ~~~ */
        rows.append({
            "score": int(sc),
            "offset": [int(start), int(end)],
            "source_text": getattr(s, "path", "") or "",
            "completed_sentence": s.original,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:top_k]
