from __future__ import annotations
from typing import Optional, List
from .models import AutoCompleteData, Sentence
from .normalize import normalize_only
from .DB.index import KGramIndex
from .config import TOP_K
import re
from . import config as CFG
import bisect

# Normalize and clean the query string for prefix matching

# /* ~~~ keep only letters+spaces, lowercase; drop punctuation ~~~ */
_KEEP = re.compile(r"[a-z ]")

_WORD = r"\w+"

# Penalty tables by 1-based position
_REPLACE = {1: 5, 2: 4, 3: 3, 4: 2}
_INSERT_DEL = {1: 10, 2: 8, 3: 6, 4: 4}


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

def _compile_prefix_pattern(query_norm: str, trailing_space: bool) -> re.Pattern:
    toks = re.findall(r"\w+", query_norm)
    if not toks:
        return re.compile(r"$a")
    if trailing_space:
        head = r"\s+".join(re.escape(t) for t in toks)
        return re.compile(rf"\b{head}\s+\w+")
    if len(toks) == 1:
        pfx = re.escape(toks[0])
        return re.compile(rf"\b{pfx}\w*")
    head = r"\s+".join(re.escape(t) for t in toks[:-1])
    pfx  = re.escape(toks[-1])
    return re.compile(rf"\b{head}\s+{pfx}\w*")

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

# --- NEW: query augmentation (1-edit correction per token, using lexicon) ---

def _within_1_edit(a: str, b: str) -> tuple[bool, int]:
    """
    Return (ok, penalty) where ok=True iff a and b are within ONE edit
    (substitution OR single added/missing letter). Penalty uses your tables.
    """
    if a == b:
        return True, 0

    if abs(len(a) - len(b)) > 1:
        return False, 0

    if len(a) == len(b):
        pos = _hamming_one(a, b)
        if pos is None:
            return False, 0
        return True, -_REPLACE.get(pos, 1)

    # insertion/deletion (length diff == 1)
    if len(a) == len(b) + 1:
        pos = _one_added_in_query(a, b)  # a has the extra char
        if pos is None:
            return False, 0
        return True, -_INSERT_DEL.get(pos, 2)
    else:  # len(b) == len(a) + 1
        pos = _one_missing_in_query(a, b)  # a is missing a char
        if pos is None:
            return False, 0
        return True, -_INSERT_DEL.get(pos, 2)


def _lexicon_terms(index) -> list[str]:
    """
    Access the word lexicon built in KGramIndex. Falls back to [] if missing.
    """
    return getattr(index, "_term_lex", []) or []


def _term_freq(index, term: str) -> int:
    """
    Heuristic frequency for tie-breaking corrections.
    Uses postings length if available; else 0.
    """
    postings = getattr(index, "_postings", None)
    if isinstance(postings, dict) and term in postings:
        return len(postings[term])
    return 0


def augment_query(query_raw: str, index) -> dict:
    """
    Correct each token by at most ONE edit (substitute OR single add/miss),
    choosing from terms in the corpus lexicon.

    Preference:
      1) higher term frequency
      2) alphabetic terms when the token has any letters
      3) less severe penalty (closer to 0)
      4) lexicographic
    """
    import re, bisect

    trailing_space = query_raw.endswith(" ")
    q_norm = normalize_only(query_raw)
    toks = re.findall(r"\w+", q_norm)

    if not toks:
        return {"original": query_raw, "corrected": query_raw, "total_penalty": 0,
                "token_map": [], "trailing_space": trailing_space}

    L = getattr(index, "_term_lex", []) or []
    postings = getattr(index, "_postings", {}) or {}

    def term_freq(term: str) -> int:
        lst = postings.get(term)
        return len(lst) if isinstance(lst, list) else 0

    def within_1_edit(a: str, b: str) -> tuple[bool, int]:
        if a == b:
            return True, 0
        if abs(len(a) - len(b)) > 1:
            return False, 0
        if len(a) == len(b):
            pos = _hamming_one(a, b)
            return (True, -_REPLACE.get(pos, 1)) if pos is not None else (False, 0)
        if len(a) == len(b) + 1:
            pos = _one_added_in_query(a, b)   # a has the extra char
            return (True, -_INSERT_DEL.get(pos, 2)) if pos is not None else (False, 0)
        pos = _one_missing_in_query(a, b)     # a is missing a char
        return (True, -_INSERT_DEL.get(pos, 2)) if pos is not None else (False, 0)

    corrected: list[str] = []
    token_map: list[tuple[str, str, int]] = []
    total_penalty = 0

    for tok in toks:
        i = bisect.bisect_left(L, tok)
        if i < len(L) and L[i] == tok:
            corrected.append(tok)
            token_map.append((tok, tok, 0))
            continue

        band = 3000
        lo = max(0, i - band); hi = min(len(L), i + band)
        tok_has_alpha = any('a' <= c <= 'z' for c in tok)
        tok_len = len(tok)

        def choose_range(iterable, alpha_only: bool):
            best_term: str | None = None
            best_tf = -1
            best_pen = -10_000
            for term in iterable:
                # quick length filter to cut work
                tl = len(term)
                if tl < tok_len - 1 or tl > tok_len + 1:
                    continue
                if alpha_only and not term.isalpha():
                    continue
                if tok_has_alpha and any(ch.isdigit() for ch in term):
                    continue  # ban numeric/alnum if token has letters
                ok, pen = within_1_edit(tok, term)
                if not ok:
                    continue
                tf = term_freq(term)
                if (best_term is None or
                    tf > best_tf or
                    (tf == best_tf and pen > best_pen) or
                    (tf == best_tf and pen == best_pen and term < best_term)):
                    best_term, best_tf, best_pen = term, tf, pen
            return best_term, best_pen

        # 1) Local band (fast)
        best_term, best_pen = (None, 0)
        if tok_has_alpha:
            best_term, best_pen = choose_range(L[lo:hi], alpha_only=True)
            if best_term is None:
                best_term, best_pen = choose_range(L[lo:hi], alpha_only=False)
        else:
            best_term, best_pen = choose_range(L[lo:hi], alpha_only=False)

        # 2) Fallback: global scan (only if nothing found in band OR token mixes digits+letters)
        tok_has_digit = any('0' <= c <= '9' for c in tok)
        if best_term is None and (tok_has_digit and tok_has_alpha):
            # try alphabetic-only first across the full lexicon
            best_term, best_pen = choose_range(L, alpha_only=True)
            if best_term is None:
                best_term, best_pen = choose_range(L, alpha_only=False)

        if best_term is None:
            corrected.append(tok)
            token_map.append((tok, tok, 0))
        else:
            corrected.append(best_term)
            token_map.append((tok, best_term, best_pen))
            total_penalty += best_pen

    corrected_query = " ".join(corrected) + (" " if trailing_space else "")
    return {"original": query_raw, "corrected": corrected_query,
            "total_penalty": int(total_penalty), "token_map": token_map,
            "trailing_space": trailing_space}

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
    if getattr(CFG, "SEARCH_MODE", "substring") != "prefix":
        return complete_query_substring(query, index, top_k)

    max_terms = getattr(CFG, "MAX_PREFIX_TERMS", 5000)
    max_cands = getattr(CFG, "MAX_PREFIX_CANDIDATES", 20000)

    aug = augment_query(query, index)
    q_corr = aug["corrected"]
    trailing_space = aug["trailing_space"]

    q_corr_norm = normalize_only(q_corr)
    pat = _compile_prefix_pattern(q_corr_norm, trailing_space)
    cand_sids = index.candidates_for_prefix_query(q_corr_norm, max_terms, max_cands)

    # safety fallback if we corrected something but got no cands
    if not cand_sids and q_corr_norm != normalize_only(query):
        cand_sids = range(getattr(index, "_num_sentences", 0))

    rows = []
    for s in index.iter_sentences(cand_sids):
        m = pat.search(s.normalized)
        if not m: continue
        start, end = m.span()
        target_raw = s.original[start:end]
        sc = score_prefix_1edit(query, target_raw)  # score vs ORIGINAL
        if sc is None: continue
        rows.append({
            "score": int(sc),
            "offset": [int(start), int(end)],
            "source_text": getattr(s, "path", "") or "",
            "completed_sentence": s.original,
            "query_original": query,
            "query_corrected": q_corr,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:top_k]

