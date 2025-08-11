from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "short.txt").write_text("a line with a lone a\n", encoding="utf-8")
    return str(root)

@pytest.mark.e2e
def test_empty_and_single_char_query(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=[roots], db_dsn="memory://")
        empty = eng.complete("", top_k=5)
        assert isinstance(empty, list) and empty == []
        single = eng.complete("a", top_k=5)
        assert isinstance(single, list)  # allow either [] or some hits; just don't crash
    finally:
        eng.shutdown()
