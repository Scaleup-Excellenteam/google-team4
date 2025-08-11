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
        Recall-safe candidate selection:
          * If len(query)<K or no gram hits → scan all sentences (spec).
          * Else UNION postings across all query grams (keeps ≤1-edit recall),
            then, if too large, keep the IDs with the most gram hits (soft cap).
        """
        assert self._get_sentence is not None
        if len(query_norm) < GRAM:
            return set(range(self._num_sentences))

        grams = list(kgrams(query_norm, GRAM))
        if not grams:
            return set(range(self._num_sentences))

        postings: List[Set[int]] = [self.bst.get(g) for g in grams]
        nonempty = [s for s in postings if s]
        if not nonempty:
            # no k-gram present in the index → spec fallback
            return set(range(self._num_sentences))

        # Count gram hits per sentence (avoids building a giant union set first)
        counts = Counter()
        for s in nonempty:
            for sid in s:
                counts[sid] += 1

        if not counts:
            return set(range(self._num_sentences))

        # If under the cap, return all; otherwise keep top-K by gram-hit count
        if MAX_CANDIDATES and len(counts) > MAX_CANDIDATES:
            top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_CANDIDATES]
            return {sid for sid, _ in top}
        else:
            return set(counts.keys())

    def iter_sentences(self, ids: Iterable[int]):
        assert self._get_sentence is not None
        for sid in ids:
            yield self._get_sentence(int(sid))
