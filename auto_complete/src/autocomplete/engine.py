from __future__ import annotations
from typing import List
from .models import Corpus, Sentence
from . import loader

class Engine:
    """
    Holds the loaded corpus. Use add_document(path, text) to ingest.
    """
    def __init__(self) -> None:
        self.corpus = Corpus(sentences=[])
        self._next_id = 0

    def add_document(self, path: str, text: str) -> None:
        # build cumulative offsets per line including EOLs
        with_eol = text.splitlines(keepends=True)
        cumul: List[int] = []
        cur = 0
        for chunk in with_eol:
            cur += len(chunk)
            cumul.append(cur)
        # store prefix sums for absolute file offsets
        self.corpus.file_prefix_sums[path] = cumul

        # create Sentence objects (original line without trailing EOL)
        lines = text.splitlines()
        for i, orig in enumerate(lines, start=1):
            norm = loader.normalize(orig)
            if not norm:
                # keep empty lines out of index but still keep for offsets if desired
                pass
            self.corpus.sentences.append(
                Sentence(
                    id=self._next_id,
                    path=path,
                    line_no=i,
                    original=orig,
                    normalized=norm
                )
            )
            self._next_id += 1

    def query(self, prefix: str, k: int = 5):
        from . import search
        return search.run(self.corpus, prefix, k=k)

def build_index_fast(engine: Engine) -> None:
    """
    Fast ingestion from DATA_ROOT with parallel I/O.
    """
    for path, text in loader.iter_documents():
        engine.add_document(path, text)
