from __future__ import annotations
from pathlib import Path

# project root: auto_complete/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# where your data files live
#DATA_ROOT = PROJECT_ROOT / "data"
DATA_ROOT = PROJECT_ROOT
# file types to include
INCLUDE_EXTS = [".txt", ".md", ".csv", ".log", ".json", ".xml"]

# folders to skip
EXCLUDE_DIRS = {".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "__pycache__"}

# reading mode:
# - "threads" for I/O-bound (fast reading)
# - "procs" for CPU-heavy per-file processing
READ_MODE = "threads"

# workers
_cpu = __import__("os").cpu_count() or 4
DEFAULT_WORKERS_THREADS = _cpu * 2
DEFAULT_WORKERS_PROCS = _cpu
WORKERS = DEFAULT_WORKERS_THREADS if READ_MODE == "threads" else DEFAULT_WORKERS_PROCS

# search/index config
TOP_K = 5
GRAM = 3               # n-gram size for the inverted index
BUILD_INDEX = True     # build index lazily on first search
