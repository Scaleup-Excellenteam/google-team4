from __future__ import annotations
import os
from collections import Counter, defaultdict
from typing import Set, Iterable, List, Tuple, Dict, Callable
from ..bst import BST
from ..models import Corpus, Sentence
from ..normalize import kgrams
from ..config import GRAM, MAX_CANDIDATES

VERBOSE = os.environ.get("AUTOCOMPLETE_VERBOSE") == "1"

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