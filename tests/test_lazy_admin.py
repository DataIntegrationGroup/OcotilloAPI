import os
from collections.abc import Iterable

from core.factory import create_api_app
from fastapi.testclient import TestClient


def _iter_route_paths(routes: Iterable) -> Iterable[str]:
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            yield path
        nested = getattr(route, "routes", None)
        if nested:
            yield from _iter_route_paths(nested)


def _has_admin_route(routes: Iterable) -> bool:
    return any(path.startswith("/admin") for path in _iter_route_paths(routes))


def test_admin_is_lazy_loaded_on_first_admin_request():
    os.environ["SESSION_SECRET_KEY"] = "test-session-secret-key"
    app = create_api_app()

    assert not _has_admin_route(app.routes)
    assert getattr(app.state, "admin_configured", False) is False

    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code in {200, 302, 307}
    assert app.state.admin_configured is True
    assert _has_admin_route(app.routes)
