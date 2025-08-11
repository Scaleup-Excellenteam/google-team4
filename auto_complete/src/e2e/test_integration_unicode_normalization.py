from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "mix.txt").write_text(
        "Café con leche.\n"
        "A naïve approach appears here.\n",
        encoding="utf-8",
    )
    return str(root)

@pytest.mark.e2e
def test_unicode_and_accents(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=[roots], db_dsn="memory://")
        assert eng.complete("cafe con leche", top_k=5), "accent-insensitive match failed"
        assert eng.complete("naive approach", top_k=5), "diaeresis-insensitive match failed"
    finally:
        eng.shutdown()
