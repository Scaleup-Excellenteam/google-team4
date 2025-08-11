from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "doc.txt").write_text(
        "All your base are belong to us.\nThe quick brown fox jumps over the lazy dog.\n",
        encoding="utf-8",
    )
    return str(root)

@pytest.mark.e2e
def test_result_schema_sanity(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine()
    try:
        eng.build(roots=[roots], db_dsn="memory://")
        rows = eng.complete("quick brown", top_k=5)
        assert rows, "expected at least one result"
        for r in rows:
            for k in ("completed_sentence", "source_text", "offset", "score"):
                assert hasattr(r, k), f"missing field {k}"
    finally:
        eng.shutdown()
