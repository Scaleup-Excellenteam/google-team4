from pathlib import Path
import pytest
from backend.engine import Engine

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"
    root.mkdir()
    (root / "q.txt").write_text(
        "To be, or not to be: that is the question.\n", encoding="utf-8"
    )
    return str(root)

@pytest.mark.e2e
def test_persist_acx_cdb_and_reload(tmp_path: Path):
    roots = _seed(tmp_path)
    acx = tmp_path / "k3.acx"
    cdb = tmp_path / "corpus.cdb"

    e1 = Engine()
    e1.build(roots=[roots], db_dsn=f"sqlite:///{cdb}", acx_out=str(acx))
    e1.shutdown()

    assert acx.exists()
    assert cdb.exists()

    e2 = Engine()
    try:
        e2.load(acx=str(acx), db_dsn=f"sqlite:///{cdb}")
        rows = e2.complete("question", top_k=3)
        assert rows and any("question" in r.completed_sentence.lower() for r in rows)
    finally:
        e2.shutdown()
