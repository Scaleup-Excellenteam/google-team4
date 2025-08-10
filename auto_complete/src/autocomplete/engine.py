"""
Core Engine Module for Autocomplete System

This module serves as the main interface for the autocomplete engine, providing
functions to load text corpora and retrieve completion suggestions. It acts as
a coordinator between the corpus loader, search algorithms, and data models.

The engine maintains a global corpus instance and provides a clean API for
external callers to interact with the autocomplete system.

Key Functions:
    load_corpus(paths): Load and initialize the corpus from specified paths
    get_best_k_completions(prefix): Retrieve top-k completion suggestions

Global State:
    _corpus: Singleton corpus instance loaded into memory

Dependencies:
    - models: Data structures for corpus and completion results
    - config: Configuration constants like TOP_K
    - loader: Corpus loading functionality
    - search: Search and scoring algorithms (optional)

Author: Google Team 4
"""

# src/autocomplete/engine.py
from typing import Iterable, List
from .models import Corpus, AutoCompleteData
from .config import TOP_K
from . import loader

# Global corpus instance - loaded once and reused
_corpus: Corpus | None = None

def load_corpus(paths: Iterable[str]) -> Corpus:
    """
    Load text corpus from specified file paths into memory.
    
    This function scans the provided directories for .txt files, loads their
    contents, normalizes the text, and creates an in-memory corpus structure.
    The corpus is stored globally and can be accessed by other functions.
    
    Args:
        paths: Iterable of directory paths to scan for .txt files
        
    Returns:
        Corpus: Loaded corpus object containing all sentences and metadata
        
    Example:
        corpus = load_corpus(['/path/to/books', '/path/to/articles'])
        print(f"Loaded {len(corpus.sentences)} sentences")
        
    Note:
        This function modifies the global _corpus variable. Subsequent calls
        will replace the existing corpus with new data.
    """
    global _corpus
    _corpus = loader.load_corpus(paths)
    return _corpus

def get_best_k_completions(prefix: str) -> List[AutoCompleteData]:
    """
    Retrieve the best k completion suggestions for a given prefix.
    
    This function delegates the actual search and scoring to the search module
    if it's available. It returns an empty list until the search implementation
    is complete.
    
    Args:
        prefix: The text prefix to find completions for
        
    Returns:
        List[AutoCompleteData]: Ranked list of completion suggestions, each
        containing the completed sentence, source file, offset, and score
        
    Raises:
        RuntimeError: If no corpus has been loaded via load_corpus()
        
    Example:
        completions = get_best_k_completions("hello wo")
        for comp in completions:
            print(f"{comp.score}: {comp.completed_sentence}")
            
    Note:
        Currently returns empty list until search.run() is implemented.
        The function is designed to gracefully handle missing search module.
    """
    global _corpus
    if _corpus is None:
        raise RuntimeError("corpus not loaded. call load_corpus(paths) first.")
    try:
        from . import search  # B's module
        return search.run(_corpus, prefix, TOP_K)
    except Exception:
        return []
