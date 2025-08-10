"""
Corpus Loading and Text Normalization Module

This module handles the loading of text files into memory and provides
text normalization functions that ensure consistent matching between
user input and corpus content.

The loader scans directories for text files, processes each line into
Sentence objects, and maintains metadata about file positions and
character offsets for accurate result reporting.

Key Functions:
    load_corpus(roots): Main function to load corpus from directory paths
    normalize(text): Standardize text for consistent matching
    _iter_txt_files(roots): Find all .txt files in specified directories
    _best_relpath(p, roots): Determine best relative path for file

Text Normalization Process:
    1. Convert to lowercase (casefold)
    2. Remove punctuation and symbols (Unicode-aware)
    3. Collapse multiple whitespace into single spaces
    4. Trim leading/trailing whitespace

Author: Google Team 4
"""

# src/autocomplete/loader.py
from pathlib import Path
from typing import Iterable, List, Dict
import re
import unicodedata

from .models import Sentence, Corpus
from .config import ENCODING, GLOB_PATTERN

# Regular expression for collapsing whitespace
_ws_re = re.compile(r"\s+")

def _strip_punct_and_symbols(s: str) -> str:
    """
    Remove punctuation and symbols from text while preserving letters, numbers, and spaces.
    
    This function uses Unicode categories to identify and remove punctuation
    and symbols. It replaces removed characters with spaces to avoid
    accidental word joins, which are later collapsed.
    
    Args:
        s: Input string to process
        
    Returns:
        str: String with punctuation and symbols replaced by spaces
        
    Example:
        >>> _strip_punct_and_symbols("Hello, world! 123")
        'Hello  world  123'
    """
    # keep letters/numbers/spaces; drop punctuation & symbols (unicode-aware)
    chars = []
    for ch in s:
        cat = unicodedata.category(ch)
        if ch.isspace() or cat.startswith("L") or cat.startswith("N"):
            chars.append(ch)
        else:
            # replace with space to avoid accidental word joins, collapse later
            chars.append(" ")
    return "".join(chars)

def normalize(text: str) -> str:
    """
    Normalize text for consistent matching between user input and corpus.
    
    This function applies a series of transformations to standardize text:
    1. Convert to lowercase (casefold)
    2. Remove punctuation and symbols
    3. Collapse multiple whitespace into single spaces
    4. Trim leading and trailing whitespace
    
    This normalization must be applied consistently to both corpus text
    and search queries to ensure proper matching.
    
    Args:
        text: Raw text string to normalize
        
    Returns:
        str: Normalized text ready for matching
        
    Example:
        >>> normalize("Hello, World!  How are you?")
        'hello world how are you'
        
    Note:
        This function is shared between loader and search modules.
        Any changes must be synchronized to maintain consistency.
    """
    s = text.casefold()
    s = _strip_punct_and_symbols(s)
    s = _ws_re.sub(" ", s).strip()
    return s

def _iter_txt_files(roots: Iterable[str]) -> List[Path]:
    """
    Find all .txt files in the specified directory trees.
    
    Recursively searches through each root directory for files matching
    the GLOB_PATTERN (default: "*.txt"). Returns a sorted list of
    file paths for reproducible loading order.
    
    Args:
        roots: Iterable of directory paths to search
        
    Returns:
        List[Path]: Sorted list of .txt file paths found
        
    Example:
        >>> files = _iter_txt_files(['/path/to/books', '/path/to/articles'])
        >>> len(files)
        15
        >>> files[0].name
        'chapter1.txt'
    """
    files: List[Path] = []
    for root in roots:
        for p in Path(root).rglob(GLOB_PATTERN):
            if p.is_file():
                files.append(p)
    # stable order for reproducibility
    files.sort()
    return files

def _best_relpath(p: Path, roots: Iterable[str]) -> str:
    """
    Determine the best relative path for a file given multiple root directories.
    
    Attempts to find the shortest relative path from any of the provided
    root directories. Falls back to the filename if no relative path can
    be determined.
    
    Args:
        p: Path object for the file
        roots: Iterable of root directory paths
        
    Returns:
        str: Best relative path or filename as fallback
        
    Example:
        >>> _best_relpath(Path('/books/fiction/novel.txt'), ['/books', '/articles'])
        'fiction/novel.txt'
        
    Note:
        This function handles cases where files might be accessible from
        multiple root directories by choosing the first valid relative path.
    """
    # choose the first root that works; fallback to basename
    for root in roots:
        try:
            rel = p.relative_to(Path(root))
            return rel.as_posix()
        except Exception:
            continue
    return p.name

def load_corpus(roots: Iterable[str]) -> Corpus:
    """
    Load text corpus from multiple directory roots into memory.
    
    This is the main function for corpus loading. It scans the specified
    directories for .txt files, processes each line into Sentence objects,
    and builds metadata structures for efficient searching and result reporting.
    
    The function maintains character offset information for each file,
    enabling accurate reporting of match positions in search results.
    
    Args:
        roots: Iterable of directory paths to scan for .txt files
        
    Returns:
        Corpus: Complete corpus object with all sentences and metadata
        
    Example:
        >>> corpus = load_corpus(['/path/to/books', '/path/to/articles'])
        >>> len(corpus.sentences)
        1250
        >>> corpus.sentences[0].path
        'books/novel.txt'
        
    Note:
        Files are processed in sorted order for reproducibility.
        Character offsets include line endings as they appear in the file.
        The function handles encoding errors gracefully by ignoring problematic characters.
    """
    sentences: List[Sentence] = []
    file_prefix_sums: Dict[str, List[int]] = {}

    next_id = 0
    for p in _iter_txt_files(roots):
        rel = _best_relpath(p, roots)

        cumul: List[int] = []
        total = 0
        with p.open("r", encoding=ENCODING, errors="ignore") as f:
            for line_no, raw in enumerate(f, start=1):
                # keep exactly as read (raw includes newline except possibly last line)
                original = raw.rstrip("\n\r")
                normalized = normalize(original)

                sentences.append(Sentence(
                    id=next_id,
                    path=rel,
                    line_no=line_no,
                    original=original,
                    normalized=normalized,
                ))
                next_id += 1

                total += len(raw)     # counts characters including EOL as present
                cumul.append(total)

        file_prefix_sums[rel] = cumul

    return Corpus(sentences=sentences, file_prefix_sums=file_prefix_sums)
