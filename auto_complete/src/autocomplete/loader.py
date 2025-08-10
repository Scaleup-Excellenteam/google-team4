"""
Text loader module for autocomplete functionality.

This module provides utilities for loading and preprocessing text data from files.
It handles text normalization for consistent processing and provides efficient
parallel file reading capabilities for building autocomplete corpora.
"""

from __future__ import annotations
from typing import Iterator, Tuple
import unicodedata

from .config import DATA_ROOT, INCLUDE_EXTS, WORKERS, EXCLUDE_DIRS, READ_MODE
from .fast_dir_ingest import parallel_read

def normalize(s: str) -> str:
    """
    Normalize text for consistent autocomplete processing.
    
    This function performs several text normalization steps to ensure consistent
    processing across different text inputs:
    1. Converts to lowercase using casefold() for better Unicode support
    2. Removes punctuation and symbols
    3. Normalizes whitespace (collapses multiple spaces into single spaces)
    4. Strips leading/trailing whitespace
    
    Args:
        s (str): The input string to normalize.
        
    Returns:
        str: The normalized string with consistent casing, spacing, and 
             punctuation removed.
             
    Examples:
        >>> normalize("Hello,  World!")
        'hello world'
        >>> normalize("  Multiple   Spaces  ")
        'multiple spaces'
        >>> normalize("Punctuation... Symbols@#$")
        'punctuation symbols'
    """
    # Convert to lowercase using casefold for better Unicode support
    s = s.casefold()
    out_chars = []
    prev_space = False
    
    for ch in s:
        if ch.isspace():
            # Collapse multiple whitespace characters into single space
            if not prev_space:
                out_chars.append(" ")
            prev_space = True
            continue
            
        if unicodedata.category(ch).startswith(("P", "S")):
            # Skip punctuation (P*) and symbols (S*) categories
            continue
            
        # Keep alphanumeric and other valid characters
        out_chars.append(ch)
        prev_space = False
        
    return "".join(out_chars).strip()

def iter_documents() -> Iterator[Tuple[str, str]]:
    """
    Iterate over all documents in the configured data directory.
    
    This function provides a high-level interface for reading all text files
    from the configured data root directory. It uses parallel processing for
    efficient file reading and applies filtering based on file extensions
    and directory exclusions.
    
    The function leverages the parallel_read utility with configuration values
    from the config module to provide fast, concurrent file processing.
    
    Yields:
        Tuple[str, str]: A tuple containing (file_path, file_content) for each
                        processed file. The file_path is the full path to the file,
                        and file_content is the text content of the file.
                        
    Configuration Dependencies:
        - DATA_ROOT: Root directory to scan for files
        - READ_MODE: File reading mode (e.g., 'r', 'rb')
        - WORKERS: Number of parallel workers for file processing
        - INCLUDE_EXTS: Set of file extensions to include
        - EXCLUDE_DIRS: Set of directory names to exclude from scanning
        
    Examples:
        >>> for path, content in iter_documents():
        ...     print(f"Processing: {path}")
        ...     # Process the file content
        ...     break
        Processing: /path/to/data/file1.txt
        
    Note:
        This function is a generator and processes files lazily, making it
        memory-efficient for large document collections.
    """
    yield from parallel_read(
        root=DATA_ROOT,
        mode=READ_MODE,
        workers=WORKERS,
        exts=INCLUDE_EXTS,
        exclude_dirs=EXCLUDE_DIRS,
    )
