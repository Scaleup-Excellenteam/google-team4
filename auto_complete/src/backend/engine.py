# backend/engine.py
from __future__ import annotations

import os
import logging
from typing import Iterable, Optional, Callable

from . import config as CFG
from .models import Corpus, Sentence
from .loader import load_corpus
from .search import complete_query
from .DB.index import KGramIndex
from .DB.storage import save_index, load_index

# ACX is optional; guard imports so the engine works without it.
try:
    from .DB.storage import save_acx_from_bst, load_acx  # type: ignore
    _HAS_ACX = True
except Exception:  # pragma: no cover
    _HAS_ACX = False

from .DB.api import CorpusStore, make_store

log = logging.getLogger(__name__)


class Engine:
    """
    Thin orchestration layer that glues together:
      - corpus storage (CRUD) via a CorpusStore (SQLite or in-memory),
      - K-gram index (KGramIndex),
      - search/ranking pipeline (search.complete_query).

    Public API (used by CLI/Flask):
      * build(roots, ...): ingest -> index -> (optional) persist -> attach store
      * load(...):         load index from cache/ACX -> attach store
      * complete(query, top_k): return ranked completions
      * shutdown():        close underlying resources

    Storage DSNs (via backend.DB.api.make_store):
      - "sqlite:///path/to/corpus.sqlite"
      - "memory://"
    """

    # ------------- lifecycle -------------

    def __init__(self) -> None:
        self.index: Optional[KGramIndex] = None
        self._store: Optional[CorpusStore] = None
        self._in_memory_corpus: Optional[Corpus] = None  # used if running without SQLite

    # /* ~~~ Build an index from source folders and wire up storage ~~~ */
    def build(
        self,
        roots: Iterable[str],
        *,
        cache: Optional[str] = None,           # path to pickle cache for index (legacy)
        db_dsn: Optional[str] = None,          # e.g., "sqlite:///./corpus.sqlite" or "memory://"
        unit: Optional[str] = None,            # "line" | "paragraph" | "window"
        window_size: Optional[int] = None,
        window_step: Optional[int] = None,
        verbose: bool = False,
        acx_out: Optional[str] = None,         # if provided and ACX available → persist ACX index
    ) -> None:
        if verbose:
            logging.basicConfig(level=logging.INFO)
            os.environ["AUTOCOMPLETE_VERBOSE"] = "1"

        # Optionally override loader/tokenization config for this build
        if unit is not None:
            CFG.TEXT_UNIT = unit
        if window_size is not None:
            CFG.WINDOW_SIZE = int(window_size)
        if window_step is not None:
            CFG.WINDOW_STEP = int(window_step)

        roots = list(roots)
        if not roots:
            raise ValueError("build(): at least one root folder is required")

        log.info("Loading corpus from %s", roots)
        corpus: Corpus = load_corpus(roots)  # materializes normalized sentences
        self._in_memory_corpus = corpus

        # Build a fresh K-gram index from the corpus
        log.info("Building K-gram index")
        idx = KGramIndex()
        idx.build(corpus)

        # -- persist index safely: temporarily detach unpicklable getter --
        orig_getter = getattr(idx, "_get_sentence", None)
        orig_count  = getattr(idx, "_num_sentences", 0)
        idx._get_sentence = None  # make object picklable
        try:
            if acx_out:
                if not _HAS_ACX:
                    raise RuntimeError("ACX persistence requested but ACX support is unavailable")
                save_acx_from_bst(idx.bst, acx_out)
            if cache:
                save_index(idx, cache)
        finally:
            # restore for the rest of build(), then we'll attach the real store below
            idx._get_sentence = orig_getter
            idx._num_sentences = orig_count


        # Persist index if requested
        if acx_out:
            if not _HAS_ACX:
                raise RuntimeError("ACX persistence requested but ACX support is unavailable")
            log.info("Saving ACX index to %s", acx_out)
            save_acx_from_bst(idx.bst, acx_out)  # uses the underlying BST/ACX structure

        if cache:
            log.info("Saving pickle index to %s", cache)
            save_index(idx, cache)

        # Choose a storage implementation and seed it with the corpus if needed
        dsn = db_dsn or "memory://"
        log.info("Initializing corpus store: %s", dsn)
        self._store = make_store(dsn, corpus=corpus)

        

        if self._store.count() == 0:               # seed SQLite on first build
            self._store.bulk_create(corpus.sentences)

        # Attach a thin getter/count to the index (decouples index from storage details)
        self._attach_index(idx, getter=self._store.read, count=self._store.count())

        # Commit engine state
        self.index = idx
        log.info("Engine build() complete: sentences=%d", self._store.count())

    # /* ~~~ Load an already-built index and wire up storage ~~~ */
    def load(
        self,
        *,
        cache: Optional[str] = None,           # pickle path for KGramIndex
        acx: Optional[str] = None,             # ACX file (preferred when present)
        db_dsn: Optional[str] = None,          # required unless an in-memory corpus already exists
        verbose: bool = False,
    ) -> None:
        if verbose:
            logging.basicConfig(level=logging.INFO)
            os.environ["AUTOCOMPLETE_VERBOSE"] = "1"

        # Choose the index source (ACX > pickle)
        if acx:
            if not _HAS_ACX:
                raise RuntimeError("ACX index path provided but ACX support is unavailable")
            if not os.path.exists(acx):
                raise FileNotFoundError(acx)
            log.info("Loading ACX index from %s", acx)
            idx = KGramIndex()
            idx.bst = load_acx(acx)  # ACX loader returns a structure compatible with .bst
        elif cache:
            if not os.path.exists(cache):
                raise FileNotFoundError(cache)
            log.info("Loading pickle index from %s", cache)
            idx = load_index(cache)
        else:
            raise ValueError("load(): require either --cache or --acx to load an index")

        # Resolve a corpus store; prefer explicit DB. Fallback to in-memory corpus if available.
        if db_dsn:
            dsn = db_dsn
        elif self._in_memory_corpus is not None:
            dsn = "memory://"
        else:
            raise ValueError("load(): db_dsn is required unless an in-memory corpus is already present")

        log.info("Initializing corpus store: %s", dsn)
        self._store = make_store(dsn, corpus=self._in_memory_corpus)

        # Attach storage to index
        self._attach_index(idx, getter=self._store.read, count=self._store.count())
        self.index = idx
        log.info("Engine load() complete: sentences=%d", self._store.count())

    # ------------- query -------------

    # /* ~~~ Run autocomplete for a user query and return ranked candidates ~~~ */
    def complete(self, query: str, *, top_k: int = CFG.TOP_K):
        if not self.index:
            raise RuntimeError("Engine not initialized. Call build() or load() first.")
        return complete_query(query, self.index, top_k=top_k)

    # ------------- teardown -------------

    # /* ~~~ Close underlying resources (DB handles, etc.) ~~~ */
    def shutdown(self) -> None:
        try:
            if self._store:
                self._store.close()
        finally:
            self._store = None
            self.index = None
            log.info("Engine shutdown complete")

    # ------------- internals -------------

    def _attach_index(self, idx: KGramIndex, *, getter: Callable[[int], Sentence], count: int) -> None:
        """
        Connect the index to a corpus provider without coupling it to a specific DB.
        Expects the KGramIndex to support an `attach_corpus(getter, count)` method.
        """
        if not hasattr(idx, "attach_corpus"):
            raise AttributeError(
                "KGramIndex is missing attach_corpus(getter, count). "
                "Please add it to your index implementation."
            )
        idx.attach_corpus(getter, count)
        log.info("Attached index to corpus store: %d sentences", count)