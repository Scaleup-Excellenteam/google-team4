from pathlib import Path
import pytest
from backend.engine import Engine
from frontend.web import app as flask_app

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "x.txt").write_text("hello world\nautocomplete demo line\n", encoding="utf-8")
    return str(root)

@pytest.mark.e2e
def test_frontend_home_page_renders(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine(); eng.build(roots=[roots], db_dsn="memory://")

    import frontend.web as webmod
    webmod._engine = eng

    client = flask_app.test_client()
    r = client.get("/")
    assert r.status_code == 200
    html = r.data.decode("utf-8", errors="ignore").lower()
    # Be permissive across templates: form or the word "autocomplete" is enough
    assert ("<form" in html) or ("autocomplete" in html)

    eng.shutdown()
