# src/autocomplete/engine.py
from typing import Iterable, List
from .models import Corpus, AutoCompleteData
from .config import TOP_K
from . import loader

_corpus: Corpus | None = None

def load_corpus(paths: Iterable[str]) -> Corpus:
    global _corpus
    _corpus = loader.load_corpus(paths)
    return _corpus

def get_best_k_completions(prefix: str) -> List[AutoCompleteData]:
    """delegates to search.run if available; returns [] until B implements it."""
    global _corpus
    if _corpus is None:
        raise RuntimeError("corpus not loaded. call load_corpus(paths) first.")
    try:
        from . import search  # B's module
        return search.run(_corpus, prefix, TOP_K)
    except Exception:
        return []
