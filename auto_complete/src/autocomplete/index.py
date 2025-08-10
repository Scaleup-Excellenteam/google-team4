"""
Index module for autocomplete functionality.

This module provides indexing capabilities for text autocomplete by building n-gram
based indices from text corpora. The index maps n-grams to sets of sentence IDs
that contain those n-grams, enabling fast lookup for autocomplete suggestions.
"""

from collections import defaultdict
from typing import Dict, Set, Iterable
from .models import Corpus

def _grams(s: str, g: int) -> Iterable[str]:
    """
    Generate n-grams from a given string.
    
    This function creates all possible n-grams of length 'g' from the input string.
    If the string is shorter than the gram length, it returns all possible substrings
    of the string instead.
    
    Args:
        s (str): The input string to generate n-grams from.
        g (int): The length of each n-gram to generate.
        
    Returns:
        Iterable[str]: An iterable of n-gram strings.
        
    Examples:
        >>> list(_grams("hello", 3))
        ['hel', 'ell', 'llo']
        >>> list(_grams("hi", 3))
        ['h', 'i', 'hi']
    """
    n = len(s)
    if n == 0:
        return []
    if n < g:
        # If string is shorter than gram length, return all possible substrings
        return (s[i:j] for i in range(n) for j in range(i+1, n+1))
    # Generate n-grams of length g using sliding window
    return (s[i:i+g] for i in range(0, n-g+1))

def build(corpus: Corpus, gram: int = 3) -> Dict[str, Set[int]]:
    """
    Build an n-gram index from a text corpus.
    
    This function creates an inverted index that maps n-grams to sets of sentence IDs
    that contain those n-grams. The index is used for fast autocomplete lookups by
    allowing quick retrieval of all sentences containing specific n-gram patterns.
    
    Args:
        corpus (Corpus): The text corpus containing sentences to index.
        gram (int, optional): The length of n-grams to generate. Defaults to 3.
        
    Returns:
        Dict[str, Set[int]]: A dictionary mapping n-gram strings to sets of 
                           sentence IDs that contain those n-grams.
                           
    Note:
        - Only processes sentences that have normalized text (skips empty/None values)
        - Avoids duplicate n-grams within the same sentence to prevent skewed frequency
        - Returns a regular dict rather than defaultdict for cleaner interface
        
    Example:
        >>> corpus = Corpus([Sentence(id=1, normalized="hello world")])
        >>> index = build(corpus, gram=3)
        >>> 'hel' in index
        True
        >>> 1 in index['hel']
        True
    """
    # Use defaultdict for efficient set creation during building
    idx: Dict[str, Set[int]] = defaultdict(set)
    
    # Process each sentence in the corpus
    for sent in corpus.sentences:
        if not sent.normalized:
            # Skip sentences without normalized text
            continue
            
        # Track n-grams seen in this sentence to avoid duplicates
        seen = set()
        
        # Generate all n-grams for this sentence
        for g in _grams(sent.normalized, gram):
            if g not in seen:
                # Add new n-gram to seen set and index
                seen.add(g)
                idx[g].add(sent.id)
                
    # Convert to regular dict for cleaner interface
    return dict(idx)
