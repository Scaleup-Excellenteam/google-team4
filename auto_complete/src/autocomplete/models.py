from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional

@dataclass(frozen=True, slots=True)
class Sentence:
    id: int
    path: str          
    line_no: int       
    original: str      # verbatim (no trailing EOL)
    normalized: str    # casefolded, punctuation removed, spaces collapsed

@dataclass(slots=True)
class Corpus:
    sentences: List[Sentence]
    index: Optional[Dict[str, Set[int]]] = None
    # cumulative file chars per line (including EOLs as read)
    file_prefix_sums: Dict[str, List[int]] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class AutoCompleteData:
    completed_sentence: str
    source_text: str
    offset: int        
    score: int
