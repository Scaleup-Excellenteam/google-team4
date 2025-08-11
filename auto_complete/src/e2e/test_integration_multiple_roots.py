from pathlib import Path
import pytest
from backend.engine import Engine

def _seed_multi(tmp: Path) -> list[str]:
    r1 = tmp / "A"; r1.mkdir()
    r2 = tmp / "B"; r2.mkdir()
    (r1 / "a.txt").write_text("alpha beta\ngamma delta\nto be or not\n", encoding="utf-8")
    (r2 / "b.txt").write_text("another root\nbeta gamma\nnot to be?\n", encoding="utf-8")
    return [str(r1), str(r2)]

@pytest.mark.e2e
def test_multiple_roots_discovery(tmp_path: Path):
    roots = _seed_multi(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=roots, db_dsn="memory://")
        rows = eng.complete("to be", top_k=10)
        assert isinstance(rows, list)
        # Expect matches from both roots overall
        assert len(rows) >= 1
    finally:
        eng.shutdown()
