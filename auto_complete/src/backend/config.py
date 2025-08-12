TOP_K: int = 5
GRAM: int = 3
NORMALIZE_PUNCTUATION: bool = True

# Candidate selection tuning
MAX_CANDIDATES: int = 15_000

# Text unit for indexing: "line", "paragraph", or "window"
TEXT_UNIT: str = "line"

# Window settings (used when TEXT_UNIT == "window")
WINDOW_SIZE: int = 3     # number of lines per window
WINDOW_STEP: int = 1     # slide by this many lines

# /* ~~~ search mode and safety caps for prefix autocomplete ~~~ */
SEARCH_MODE = "prefix"     # "prefix" (new) or "substring" (legacy)

# /* ~~~ cap how many lexicon terms we expand for short prefixes ~~~ */
MAX_PREFIX_TERMS = 5000

# /* ~~~ cap how many candidate sentences we pass to ranking ~~~ */
MAX_PREFIX_CANDIDATES = 20000
