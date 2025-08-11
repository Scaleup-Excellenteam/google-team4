from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class Sentence:
    id: int
    path: str                 # relative file path
    line_no: int              # 0-based
    original: str             # original line including punctuation
    normalized: str           # normalized form for matching
    norm_to_orig: List[int]   # map normalized char index -> original index

@dataclass
class Corpus:
    sentences: List[Sentence]

@dataclass(frozen=True)
class AutoCompleteData:
    completed_sentence: str
    source_text: str
    offset: tuple[int, int]   # (line_no, start_index_in_line) in original sentence
    score: int
