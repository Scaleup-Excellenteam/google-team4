from collections import defaultdict
from typing import Dict, Set, Iterable
from .models import Corpus

def _grams(s: str, g: int) -> Iterable[str]:
    n = len(s)
    if n == 0:
        return []
    if n < g:
        return (s[i:j] for i in range(n) for j in range(i+1, n+1))
    return (s[i:i+g] for i in range(0, n-g+1))

def build(corpus: Corpus, gram: int = 3) -> Dict[str, Set[int]]:
    idx: Dict[str, Set[int]] = defaultdict(set)
    for sent in corpus.sentences:
        if not sent.normalized:
            continue
        seen = set()
        for g in _grams(sent.normalized, gram):
            if g not in seen:
                seen.add(g)
                idx[g].add(sent.id)
    return dict(idx)
