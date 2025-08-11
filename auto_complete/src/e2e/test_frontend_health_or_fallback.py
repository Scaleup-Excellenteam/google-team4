from pathlib import Path
import pytest
from backend.engine import Engine
from frontend.web import app as flask_app

def _seed(tmp: Path) -> str:
    root = tmp / "Archive"; root.mkdir()
    (root / "y.txt").write_text("health check line\n", encoding="utf-8")
    return str(root)

@pytest.mark.e2e
def test_frontend_health_or_fallback(tmp_path: Path):
    roots = _seed(tmp_path)
    eng = Engine(); eng.build(roots=[roots], db_dsn="memory://")

    import frontend.web as webmod
    webmod._engine = eng

    client = flask_app.test_client()
    # Probe for a health route; fall back to "/"
    routes = {r.rule for r in flask_app.url_map.iter_rules()}
    health_path = next((p for p in ("/health", "/api/health", "/healthz") if p in routes), None)

    if health_path:
        r = client.get(health_path)
        assert r.status_code == 200
        data = r.get_json() or {}
        assert data.get("ok", True) is True
    else:
        r = client.get("/")
        assert r.status_code == 200

    eng.shutdown()
