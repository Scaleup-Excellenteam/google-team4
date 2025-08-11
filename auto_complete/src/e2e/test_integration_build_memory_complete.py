from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"
    root.mkdir()
    (root / "hamlet.txt").write_text(
        "To be, or not to be: that is the question.\n"
        "Whether 'tis nobler in the mind to suffer.\n",
        encoding="utf-8",
    )
    return str(root)

@pytest.mark.e2e
def test_build_memory_complete(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=[roots], db_dsn="memory://")
        rows = eng.complete("to be", top_k=5)
        assert isinstance(rows, list) and rows
        assert any("to be" in r.completed_sentence.lower() for r in rows)
    finally:
        eng.shutdown()
