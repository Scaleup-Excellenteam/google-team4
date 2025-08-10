"""
Autocomplete Engine Module

This module provides an intelligent autocomplete system that can suggest sentence
completions based on a given prefix. It loads text corpora from multiple sources,
normalizes the text for consistent matching, and returns ranked completion suggestions.

The module is designed with a clean separation of concerns:
- Corpus loading and text normalization
- Search and scoring algorithms
- Data models for sentences and results
- Configuration management

Main Functions:
    load_corpus(paths): Load text files from specified paths into memory
    get_best_k_completions(prefix): Get top-k completion suggestions for a prefix

Example Usage:
    from autocomplete import load_corpus, get_best_k_completions
    
    # Load corpus from text files
    corpus = load_corpus(['/path/to/texts', '/another/path'])
    
    # Get completions for a prefix
    completions = get_best_k_completions("hello wo")
    
    for completion in completions:
        print(f"{completion.score}: {completion.completed_sentence}")

Author: Google Team 4
Version: 1.0.0
"""

# src/autocomplete/__init__.py
from .engine import load_corpus, get_best_k_completions  # re-export

__version__ = "1.0.0"
__author__ = "Google Team 4"
__all__ = ["load_corpus", "get_best_k_completions"]
