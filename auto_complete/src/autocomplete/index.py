# src/autocomplete/index.py
from typing import Dict, Set
from .models import Corpus

def build(corpus: Corpus, gram: int = 3) -> Dict[str, Set[int]]:
    """n-gram inverted index (to be filled tomorrow if needed)."""
    return {}
