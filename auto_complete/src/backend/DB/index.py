from __future__ import annotations
import os
from collections import Counter, defaultdict
from typing import Set, Iterable, List, Tuple, Dict, Callable
from ..bst import BST
from ..models import Corpus, Sentence
from ..normalize import kgrams
from ..config import GRAM, MAX_CANDIDATES

from collections import defaultdict
import bisect, re
from typing import Dict, List, Tuple, Iterable, Iterator, Optional

_TOKEN_RE = re.compile(r"\w+")  # tokenize normalized sentences into "words"

VERBOSE = os.environ.get("AUTOCOMPLETE_VERBOSE") == "1" # Progress logging (set AUTOCOMPLETE_VERBOSE=1 to enable)

class KGramIndex:
    """
    K-gram index + corpus provider.
    For fast-start mode, bst can be a memory-mapped ACXIndex (has get(key)->Set[int]).
    Corpus is provided via a getter function to support SQLite-backed corpora.
    """
    def __init__(self) -> None:
        self.bst = BST()  # or ACXIndex in fast mode
        self._get_sentence: Callable[[int], Sentence] | None = None
        self._num_sentences: int = 0

        # /* ~~~ NEW: word-prefix structures ~~~ */
        self._term_lex: List[str] = []
        self._postings: Dict[str, List[Tuple[int, int]]] = {}  # term -> [(sid, tok_pos)

    # ---- Build (offline) ----
    def build(self, corpus: Corpus) -> None:
        # Aggregate postings per gram (fewer Python calls)
        buckets: Dict[str, Set[int]] = defaultdict(set)
        for s in corpus.sentences:
            for g in kgrams(s.normalized, GRAM):
                buckets[g].add(s.id)
        self.bst = BST.from_pairs((g, ids) for g, ids in buckets.items())
        self.attach_corpus(lambda sid: corpus.sentences[sid], len(corpus.sentences))
        if VERBOSE:
            print(f"[indexing bst done] grams={len(buckets):,}")

        # Build word prefix index
        self._build_word_prefix_index(corpus)
        

    # ---- Corpus provider ----
    def attach_corpus(self, getter: Callable[[int], Sentence], n: int) -> None:
        self._get_sentence = getter
        self._num_sentences = int(n)

    # ---- Query ----
    def candidate_ids(self, query_norm: str) -> Set[int]:
        """
        Recall-safe candidate selection with a FAST path for short queries:
        * len(query) == 0      -> no candidates
        * 1 <= len(query) < K  -> union of postings for grams that CONTAIN the short query
                                    (instead of scanning the entire corpus)
        * len(query) >= K      -> normal K-gram logic (as before)
        """
        assert self._get_sentence is not None
        q = query_norm

        if not q:
            return set()

        if len(q) < GRAM:
            counts = Counter()
            it = getattr(self.bst, "iter_items", None)
            if callable(it):
                for g, ids in it():
                    if q in g:               
                        for sid in ids:
                            counts[sid] += 1
                if counts:
                    if MAX_CANDIDATES and len(counts) > MAX_CANDIDATES:
                        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_CANDIDATES]
                        return {sid for sid, _ in top}
                    return set(counts.keys())
            # אם אין iter_items או אין פגיעות בכלל – אל תחזיר את כל הקורפוס
            return set()

        # >>> מסלול רגיל (כמו שהיה) עבור len(query) >= K <<<
        grams = list(kgrams(q, GRAM))
        if not grams:
            return set()

        postings: List[Set[int]] = [self.bst.get(g) for g in grams]
        nonempty = [s for s in postings if s]
        if not nonempty:
            return set()

        counts = Counter()
        for s in nonempty:
            for sid in s:
                counts[sid] += 1

        if not counts:
            return set()

        if MAX_CANDIDATES and len(counts) > MAX_CANDIDATES:
            top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_CANDIDATES]
            return {sid for sid, _ in top}
        else:
            return set(counts.keys())

    def iter_sentences(self, ids: Iterable[int]):
        assert self._get_sentence is not None
        for sid in ids:
            yield self._get_sentence(int(sid))

    # ---- Getters ----
    def __getstate__(self):
        # Make the object picklable by dropping the unpicklable lambda/closure.
        state = self.__dict__.copy()
        state["_get_sentence"] = None
        # keep _num_sentences as a plain int
        state["_num_sentences"] = int(state.get("_num_sentences", 0))
        return state

    # ---- Setters ----
    def __setstate__(self, state):
        # Loader will re-attach a real getter via attach_corpus()
        self.__dict__.update(state)


    # ---- Word prefix index ----
    def _build_word_prefix_index(self, corpus) -> None:
        """
        /* ~~~ Build a positional inverted index over normalized *words*.
           - For each normalized word token, store (sentence_id, token_position)
           - Keep a sorted lexicon for quick prefix scans (bisect) ~~~ */
        """
        buckets: Dict[str, List[Tuple[int,int]]] = defaultdict(list)
        for sid, s in enumerate(corpus.sentences):
            toks = _TOKEN_RE.findall(s.normalized)
            for tpos, tok in enumerate(toks):
                buckets[tok].append((sid, tpos))
        self._term_lex = sorted(buckets.keys())
        self._postings = dict(buckets)

    # ---- Candidates for prefix queries ----
    def candidates_for_prefix_query(self, query: str,
                                    max_terms: int,
                                    max_candidates: int) -> Iterable[int]:
        """
        /* ~~~ Return sentence IDs that *could* contain the query as:
               - whole words for all tokens except the last, which is a **prefix**, OR
               - a 1-edit variant (substitution / single added / single missing).
           NOTE: We keep this generous; the scorer will enforce the 1-edit rule. ~~~ */
        """
        # tokenize query (normalized earlier in search)
        q_toks = _TOKEN_RE.findall(query)
        if not q_toks:
            return []

        exact = q_toks[:-1]
        last  = q_toks[-1]

        # --- 1) prefix range for the last token in lexicon
        L = self._term_lex
        lo = bisect.bisect_left(L, last)
        hi = bisect.bisect_right(L, last + "\uffff")
        if hi - lo > max_terms:
            hi = lo + max_terms
        last_terms = L[lo:hi]

        # --- 2) expand by tokens that are within 1 edit of last (tolerant)
        def within_1_edit(a: str, b: str) -> bool:
            if a == b: return True
            if abs(len(a)-len(b)) > 1: return False
            # substitution
            if len(a) == len(b):
                return sum(x!=y for x,y in zip(a,b)) == 1
            # insert/delete
            if len(a) > len(b): a, b = b, a  # ensure a is shorter
            i = j = 0; diff = 0
            while i < len(a) and j < len(b):
                if a[i] == b[j]:
                    i += 1; j += 1
                else:
                    diff += 1; j += 1
                    if diff > 1: return False
            return True  # tail diff counts as at most one
        # add tolerant neighbors (bounded by max_terms too)
        # scan a narrow lexicon band around the last token
        w_lo = max(0, lo - 2000); w_hi = min(len(L), hi + 2000)
        for t in L[w_lo:w_hi]:
            if within_1_edit(last, t) and t not in last_terms:
                last_terms.append(t)
                if len(last_terms) >= max_terms:
                    break

        # --- aggregate sentence IDs via postings of candidate last terms
        sid_hits = set()
        for term in last_terms:
            for sid, _ in self._postings.get(term, ()):
                sid_hits.add(sid)
                if len(sid_hits) >= max_candidates:
                    return sid_hits
        return sid_hits
