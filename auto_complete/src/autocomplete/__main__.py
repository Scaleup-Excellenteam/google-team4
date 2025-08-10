"""
Command Line Interface for Autocomplete Engine

This module provides a command-line interface for the autocomplete system.
It allows users to load text corpora from specified directories and interactively
test the autocomplete functionality by entering prefixes and seeing completion suggestions.

Usage:
    python -m autocomplete <root1> [<root2> ...]

Arguments:
    root1, root2, ...: Directory paths containing .txt files to load as corpus

Features:
    - Loads text files from multiple root directories
    - Interactive prefix input for testing completions
    - Displays ranked completion results with scores and source information
    - Graceful handling of EOF and empty input

Example:
    python -m autocomplete /path/to/books /path/to/articles
    > hello wo
    85 | books/novel.txt:1234 | hello world, how are you today?
    72 | articles/tech.txt:567 | hello world program in python

Author: Google Team 4
"""

# src/autocomplete/__main__.py
import sys
from .engine import load_corpus, get_best_k_completions

def main():
    """
    Main entry point for the autocomplete command-line interface.
    
    Loads corpus from specified directories and runs an interactive loop
    where users can enter prefixes to test autocomplete functionality.
    
    The function expects at least one directory path as a command-line argument.
    It loads all .txt files from the specified directories and then enters
    an interactive mode for testing completions.
    
    Raises:
        SystemExit: If no directory paths are provided as arguments
    """
    if len(sys.argv) < 2:
        print("usage: python -m autocomplete <root1> [<root2> ...]")
        print("Example: python -m autocomplete /path/to/texts /another/path")
        sys.exit(1)

    roots = sys.argv[1:]
    print(f"Loading corpus from {len(roots)} directory(ies): {', '.join(roots)}")
    
    corpus = load_corpus(roots)
    print(f"Loaded {len(corpus.sentences)} sentences from {len(roots)} root(s).")
    print("Enter a prefix (empty line to quit)")
    print("=" * 50)

    while True:
        try:
            q = input("> ")
        except EOFError:
            print("\nExiting due to EOF")
            break
        if not q.strip():
            print("Exiting...")
            break

        results = get_best_k_completions(q)
        if not results:
            print("(no results yet; waiting for search implementation)")
        else:
            print(f"Found {len(results)} completion(s):")
            for r in results:
                print(f"{r.score:4d} | {r.source_text}:{r.offset} | {r.completed_sentence}")

if __name__ == "__main__":
    main()
