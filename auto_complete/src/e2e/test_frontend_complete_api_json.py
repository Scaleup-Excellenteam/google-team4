from pathlib import Path
import pytest
from backend.engine import Engine
from frontend.web import app as flask_app

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "h.txt").write_text("To be, or not to be: that is the question.\n", encoding="utf-8")
    return str(root)

@pytest.mark.e2e
def test_frontend_complete_api_json(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine(); eng.build(roots=[roots], db_dsn="memory://")

    import frontend.web as webmod
    webmod._engine = eng

    client = flask_app.test_client()
    rv = client.get("/api/complete?q=to%20be&k=3")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list) and data
    first = data[0]
    for key in ("completed_sentence", "source_text", "offset", "score"):
        assert key in first

    eng.shutdown()
