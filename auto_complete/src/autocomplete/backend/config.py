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
