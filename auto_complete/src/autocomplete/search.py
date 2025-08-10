from typing import List, Dict, Set, Tuple, Optional
from .models import Corpus, Sentence, AutoCompleteData
from .config import TOP_K, GRAM, BUILD_INDEX
from . import loader
from . import index as index_mod

def _grams(s: str, g: int) -> List[str]:
    n = len(s)
    if n == 0:
        return []
    if n < g:
        return [s[i:j] for i in range(n) for j in range(i+1, n+1)]
    return [s[i:i+g] for i in range(0, n-g+1)]

def _candidate_ids(corpus: Corpus, q_norm: str) -> List[int]:
    if BUILD_INDEX:
        if corpus.index is None:
            corpus.index = index_mod.build(corpus, gram=GRAM)
        if len(q_norm) >= GRAM:
            grams = _grams(q_norm, GRAM)
            sets: List[Set[int]] = []
            for g in grams:
                ids = corpus.index.get(g)
                if not ids:
                    return []
                sets.append(ids)
            cand: Set[int] = set.intersection(*sets) if sets else set()
            return sorted(cand)
    return [s.id for s in corpus.sentences]

def _exact_substring(s_norm: str, q_norm: str) -> List[int]:
    starts = []
    start = 0
    while True:
        pos = s_norm.find(q_norm, start)
        if pos == -1: break
        starts.append(pos)
        start = pos + 1
    return starts

def _replace_match(s_norm: str, q_norm: str) -> List[Tuple[int,int]]:
    n, m = len(s_norm), len(q_norm)
    out = []
    for start in range(0, n - m + 1):
        mismatches = 0
        pos = -1
        for i in range(m):
            if s_norm[start + i] != q_norm[i]:
                mismatches += 1; pos = i + 1
                if mismatches > 1: break
        if mismatches == 1:
            out.append((start, pos))
    return out

def _insert_match(s_norm: str, q_norm: str) -> List[Tuple[int,int]]:
    m = len(q_norm)
    out = []
    for i in range(m):
        q2 = q_norm[:i] + q_norm[i+1:]
        pos = s_norm.find(q2)
        if pos != -1:
            out.append((pos, i + 1))
    return out

def _delete_match(s_norm: str, q_norm: str) -> List[Tuple[int,int]]:
    n, m = len(s_norm), len(q_norm)
    win = m + 1
    out = []
    for start in range(0, n - win + 1):
        i = j = 0
        used = False
        while i < m and j < win:
            if q_norm[i] == s_norm[start + j]:
                i += 1; j += 1
            elif not used:
                used = True; j += 1  # skip one s char
            else:
                break
        if i == m:
            out.append((start, i + 1))
    return out

def _score(L: int, edit_type: Optional[str], edit_pos: Optional[int]) -> int:
    base = 2 * (L if edit_type in (None, "delete") else (L - 1))
    if edit_type is None or edit_pos is None:
        return base
    p = max(1, min(edit_pos, 5))
    pen = ({1:-5,2:-4,3:-3,4:-2,5:-1} if edit_type == "replace" else {1:-10,2:-8,3:-6,4:-4,5:-2})[p]
    return base + pen

def _offset_in_line(original: str, norm_start: int) -> int:
    s = original.casefold()
    i = 0
    n = len(s)
    norm_idx = 0
    while i < n:
        ch = s[i]
        if ch.isspace():
            j = i
            while j < n and s[j].isspace():
                j += 1
            if norm_idx != 0:
                if norm_idx == norm_start:
                    return i
                norm_idx += 1
            i = j
            continue
        import unicodedata
        if unicodedata.category(ch).startswith(("P","S")):
            i += 1
            continue
        if norm_idx == norm_start:
            return i
        norm_idx += 1
        i += 1
    return 0

def _file_offset(prefix_sums, path: str, line_no: int, offset_in_line: int) -> int:
    cumul = prefix_sums.get(path, [])
    start_of_line = 0 if line_no <= 1 else cumul[line_no - 2]
    return start_of_line + offset_in_line

def run(corpus: Corpus, prefix: str, k: int = TOP_K) -> List[AutoCompleteData]:
    q_norm = loader.normalize(prefix)
    if not q_norm:
        return []
    ids = _candidate_ids(corpus, q_norm)
    if not ids:
        return []

    by_id: Dict[int, Sentence] = {s.id: s for s in corpus.sentences}
    L = len(q_norm)

    results: List[Tuple[int, int, Optional[str], Optional[int], Sentence]] = []
    for sid in ids:
        s = by_id[sid]
        best = (-10**9, 10**9, None, None, -1)
        for st in _exact_substring(s.normalized, q_norm):
            best = max(best, (_score(L, None, None), -st, None, None, st))
        for st, pos in _replace_match(s.normalized, q_norm):
            best = max(best, (_score(L, "replace", pos), -st, "replace", pos, st))
        for st, pos in _insert_match(s.normalized, q_norm):
            best = max(best, (_score(L, "insert", pos), -st, "insert", pos, st))
        for st, pos in _delete_match(s.normalized, q_norm):
            best = max(best, (_score(L, "delete", pos), -st, "delete", pos, st))
        if best[0] == -10**9:
            continue
        score, neg_start, etype, epos, start_norm = best
        off_in_line = _offset_in_line(s.original, start_norm)
        file_off = _file_offset(corpus.file_prefix_sums, s.path, s.line_no, off_in_line)
        results.append((score, -neg_start, etype, epos, s, file_off))

    if not results:
        return []

    out: List[AutoCompleteData] = []
    seen = set()
    for score, start, etype, epos, s, file_off in results:
        key = (s.path, s.line_no, file_off, score)
        if key in seen:
            continue
        seen.add(key)
        out.append(AutoCompleteData(
            completed_sentence=s.original,
            source_text=s.path,
            offset=file_off,
            score=score
        ))
    out.sort(key=lambda r: (-r.score, r.completed_sentence))
    return out[:k]
