from __future__ import annotations

import pytest

import db.engine as engine_module


def test_build_cloudsql_url_uses_psycopg2_unix_socket(monkeypatch):
    monkeypatch.setenv("CLOUD_SQL_INSTANCE_NAME", "proj:region:instance")
    monkeypatch.setenv("CLOUD_SQL_DATABASE", "ocotillo")
    monkeypatch.setenv("CLOUD_SQL_USER", "postgres")
    monkeypatch.setenv("CLOUD_SQL_SOCKET_DIR", "/cloudsql")

    url = engine_module.build_cloudsql_url(password="secret")

    assert url.drivername == "postgresql+psycopg2"
    assert url.username == "postgres"
    assert url.password == "secret"
    assert url.database == "ocotillo"
    assert url.query["host"] == "/cloudsql/proj:region:instance"


def test_init_cloudsql_engine_injects_fresh_iam_token(monkeypatch):
    monkeypatch.setenv("CLOUD_SQL_INSTANCE_NAME", "proj:region:instance")
    monkeypatch.setenv("CLOUD_SQL_DATABASE", "ocotillo")
    monkeypatch.setenv("CLOUD_SQL_USER", "postgres")
    monkeypatch.setenv("CLOUD_SQL_IAM_AUTH", "true")

    captured: dict[str, object] = {}
    listeners: dict[str, object] = {}
    fake_engine = object()

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_engine

    def fake_listens_for(target, identifier):
        assert target is fake_engine
        assert identifier == "do_connect"

        def decorator(func):
            listeners[identifier] = func
            return func

        return decorator

    monkeypatch.setattr(engine_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(engine_module.event, "listens_for", fake_listens_for)
    monkeypatch.setattr(engine_module, "_install_pool_logging", lambda _: None)

    def fake_token_loader():
        return "token-123"

    attr_name = "get_iam_login_token"
    monkeypatch.setattr(engine_module, attr_name, fake_token_loader)

    engine = engine_module.init_cloudsql_engine()

    assert engine is fake_engine
    assert captured["url"].drivername == "postgresql+psycopg2"
    connect_params: dict[str, str] = {}
    listeners["do_connect"](None, None, (), connect_params)
    assert connect_params["password"] == "token-123"


def test_init_cloudsql_engine_requires_password_without_iam_auth(monkeypatch):
    monkeypatch.setenv("CLOUD_SQL_INSTANCE_NAME", "proj:region:instance")
    monkeypatch.setenv("CLOUD_SQL_DATABASE", "ocotillo")
    monkeypatch.setenv("CLOUD_SQL_USER", "postgres")
    monkeypatch.delenv("CLOUD_SQL_PASSWORD", raising=False)
    monkeypatch.delenv("CLOUD_SQL_IAM_AUTH", raising=False)

    with pytest.raises(RuntimeError, match="CLOUD_SQL_PASSWORD"):
        engine_module.init_cloudsql_engine()
