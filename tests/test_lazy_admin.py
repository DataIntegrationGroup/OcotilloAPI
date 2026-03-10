import os

from core.factory import create_api_app
from fastapi.testclient import TestClient


def test_admin_is_lazy_loaded_on_first_admin_request():
    os.environ["SESSION_SECRET_KEY"] = "test-session-secret-key"
    app = create_api_app()

    assert not any(route.path.startswith("/admin") for route in app.routes)
    assert getattr(app.state, "admin_configured", False) is False

    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code in {200, 302, 307}
    assert app.state.admin_configured is True
    assert any(route.path.startswith("/admin") for route in app.routes)
