from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "t.txt").write_text(
        "to be or not to be\n" * 3 + "the question remains\n", encoding="utf-8"
    )
    return str(root)

@pytest.mark.e2e
def test_topk_limit_and_result_types(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=[roots], db_dsn="memory://")
        rows = eng.complete("to be", top_k=2)
        assert isinstance(rows, list)
        assert len(rows) <= 2

        r = rows[0]
        # Basic shape
        assert hasattr(r, "completed_sentence")
        assert isinstance(r.completed_sentence, str) and r.completed_sentence

        # offset can be int OR (start, end) tuple — accept both
        off = r.offset
        if isinstance(off, int):
            assert off >= 0
        else:
            assert isinstance(off, (tuple, list)) and len(off) == 2
            s, e = off
            assert isinstance(s, int) and isinstance(e, int)
            assert s >= 0 and e >= s

        # score should be numeric
        assert isinstance(r.score, (int, float))
    finally:
        eng.shutdown()
