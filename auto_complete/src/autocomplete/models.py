# src/autocomplete/models.py
"""
Data models for the autocomplete engine.

This module defines three small, focused data containers:

- Sentence: a single corpus line (original + normalized) with stable identity.
- Corpus: the in-memory corpus plus optional acceleration structures.
- AutoCompleteData: the exact result object returned to callers.

These classes do not contain business logic; they only structure the data so
that loading, searching, and scoring remain simple and predictable.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional


@dataclass(frozen=True, slots=True)
class Sentence:
    """
    Represents one logical sentence (one line from a .txt file) in the corpus.

    Attributes
    ----------
    id : int
        A stable, incrementing identifier used to reference the sentence
        (e.g., from an inverted index). Never reused.
    path : str
        File path of the source file, relative to the provided root(s).
    line_no : int
        1-based line number within the source file.
    original : str
        The exact text of the line as read from disk (without trailing EOL).
    normalized : str
        A normalized form used for matching (casefolded, punctuation removed,
        whitespace collapsed). Must be produced by the same normalize()
        routine used by both loader and search to guarantee consistent matches.
    """
    id: int
    path: str
    line_no: int
    original: str
    normalized: str


@dataclass(slots=True)
class Corpus:
    """
    The in-memory corpus plus optional structures that speed up search.

    Attributes
    ----------
    sentences : List[Sentence]
        All sentences loaded into memory. This is the ground truth on which
        searching and scoring operate.
    index : Optional[Dict[str, Set[int]]]
        Optional n-gram inverted index mapping gram -> set of Sentence.id.
        When present, it reduces candidate sentences for substring matching.
        Can be built after loading (e.g., based on config).
    file_prefix_sums : Dict[str, List[int]]
        For each file path, a list of cumulative character counts per line,
        including line endings as they were read. Enables O(1) conversion from
        (line_no, offset_in_line) to a file-global offset:
            file_offset = prefix_sums[line_no - 1] + offset_in_line
    """
    sentences: List[Sentence]
    index: Optional[Dict[str, Set[int]]] = None
    file_prefix_sums: Dict[str, List[int]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True) # frozen=True to ensure immutability and slots=True for memory efficiency
class AutoCompleteData:
    """
    The result item returned by get_best_k_completions().

    This mirrors the exact output contract required by the project:
    the fully completed sentence, its source file path, the file-global
    character offset where the match begins, and the computed score.

    Attributes
    ----------
    completed_sentence : str
        The original sentence text to present to the user (verbatim).
    source_text : str
        The source file path (not arbitrary text). This field name is part
        of the required API even if its meaning is “source path”.
    offset : int
        Character offset within the file where the matched window starts.
        Computed via file_prefix_sums + offset within the line.
    score : int
        Deterministic score for ranking, per the project’s scoring table:
        base = 2 × matched characters; penalties for single edit by position;
        tie-break by alphabetical order of completed_sentence.
    """
    completed_sentence: str
    source_text: str
    offset: int
    score: int
