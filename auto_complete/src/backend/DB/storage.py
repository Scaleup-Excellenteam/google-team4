from __future__ import annotations
import os
import pickle
from typing import Any, Iterable, Tuple
from .acx import ACXWriter, ACXIndex
from ..config import GRAM

def save_index(index: Any, path: str) -> None:
    """Pickle (legacy)."""
    tmp = f"{path}.tmp"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)

def load_index(path: str) -> Any:
    """Unpickle (legacy)."""
    with open(path, "rb") as f:
        return pickle.load(f)

# ---- ACX (memory-mapped k-gram index) ----
def save_acx_from_bst(bst, path: str) -> None:
    writer = ACXWriter(k=GRAM)
    writer.save(path, bst.iter_items())

def load_acx(path: str) -> ACXIndex:
    return ACXIndex(path)
