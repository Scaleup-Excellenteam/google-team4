"""Public API for the autocomplete engine (fast-start ready)."""
from __future__ import annotations
import os, time
from backend.config import TOP_K
from backend.loader import load_corpus
from backend.DB.index import KGramIndex
from backend.search import complete_query
from backend.DB.storage import save_index, load_index, save_acx_from_bst, load_acx
from backend.DB.corpusdb import CorpusDB

_index: KGramIndex | None = None

def initialize(paths: list[str],
               cache: str | None = None,
               rebuild: bool = False,
               verbose: bool = False,
               acx: str | None = None,
               db: str | None = None,
               unit: str | None = None,
               window_size: int | None = None,
               window_step: int | None = None) -> None:
    """
    Init modes:
      1) Fast-start (recommended): acx + db. If rebuild or missing, build from roots using the given text unit.
      2) Legacy pickle: cache path (not recommended for huge corpora).
    """
    global _index
    t0 = time.perf_counter()

    # Fast path: load ACX + DB if present and not rebuilding
    if acx and db and (not rebuild) and os.path.exists(acx) and os.path.exists(db):
        if verbose:
            size = os.path.getsize(acx)
            print(f"[acx] mapping {acx} ({size:,} bytes) and opening DB {db}")
        idx = KGramIndex()
        mm = load_acx(acx)
        dbh = CorpusDB(db)
        idx.bst = mm
        idx.attach_corpus(dbh.get_sentence, dbh.count())
        _index = idx
        if verbose:
            print(f"[ready] init complete in {time.perf_counter() - t0:.2f}s")
        return

    # Build from roots (for ACX/DB or legacy pickle)
    if verbose:
        print(f"[build] scanning roots: {paths} (unit={unit or 'line'})")
    corpus = load_corpus(paths, unit=unit, window_size=window_size, window_step=window_step)

    idx = KGramIndex()
    if verbose:
        print("[build] building k-gram index…")
    t1 = time.perf_counter()
    idx.build(corpus)
    if verbose:
        print(f"[build] index built in {time.perf_counter() - t1:.2f}s")

    # Fast-start artifacts
    if acx and db:
        if verbose:
            print(f"[save] writing ACX to {acx} and DB to {db}")
        save_acx_from_bst(idx.bst, acx)
        CorpusDB.build_from_corpus(corpus, db)
        mm = load_acx(acx)
        dbh = CorpusDB(db)
        idx.bst = mm
        idx.attach_corpus(dbh.get_sentence, dbh.count())
        _index = idx
        if verbose:
            print(f"[ready] init complete in {time.perf_counter() - t0:.2f}s")
        return

    # Legacy pickle
    if cache:
        if verbose:
            print(f"[cache] saving index to {cache}")
        save_index(idx, cache)
    _index = idx
    if verbose:
        print(f"[ready] init complete in {time.perf_counter() - t0:.2f}s")

def complete(query: str):
    """Return top-K completions (list[AutoCompleteData])."""
    if _index is None:
        raise RuntimeError("Engine not initialized. Call initialize(...) first.")
    return complete_query(query, _index, top_k=TOP_K)
