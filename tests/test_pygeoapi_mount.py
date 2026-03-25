import types

from core import pygeoapi


def test_load_pygeoapi_app_imports_when_module_not_loaded(monkeypatch):
    fake_module = types.SimpleNamespace(APP=object())
    import_calls = []

    def fake_import_module(name):
        import_calls.append(name)
        return fake_module

    monkeypatch.delitem(
        pygeoapi.sys.modules,
        "pygeoapi.starlette_app",
        raising=False,
    )
    monkeypatch.setattr(
        pygeoapi.importlib,
        "import_module",
        fake_import_module,
    )

    app = pygeoapi._load_pygeoapi_app()

    assert app is fake_module.APP
    assert import_calls == ["pygeoapi.starlette_app"]


def test_load_pygeoapi_app_reloads_when_module_already_loaded(monkeypatch):
    existing_module = types.SimpleNamespace(APP=object())
    reloaded_module = types.SimpleNamespace(APP=object())
    reload_calls = []

    def fake_reload(module):
        reload_calls.append(module)
        return reloaded_module

    monkeypatch.setitem(
        pygeoapi.sys.modules,
        "pygeoapi.starlette_app",
        existing_module,
    )
    monkeypatch.setattr(pygeoapi.importlib, "reload", fake_reload)

    app = pygeoapi._load_pygeoapi_app()

    assert app is reloaded_module.APP
    assert reload_calls == [existing_module]
