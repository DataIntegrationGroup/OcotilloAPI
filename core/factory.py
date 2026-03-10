import os

from dotenv import load_dotenv

from core.app import create_base_app
from core.initializers import (
    configure_apitally_middleware,
    configure_cors_middleware,
    configure_lazy_admin,
    configure_session_middleware,
    register_api_routes,
)

_runtime_initialized = False


def initialize_runtime() -> None:
    global _runtime_initialized

    if _runtime_initialized:
        return

    load_dotenv(override=False)
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
            ),
            profiles_sample_rate=float(
                os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.0")
            ),
            profile_lifecycle="trace",
            send_default_pii=True,
        )

    _runtime_initialized = True


def create_api_app():
    initialize_runtime()
    app = create_base_app()
    register_api_routes(app)
    from core.pygeoapi import mount_pygeoapi

    mount_pygeoapi(app)
    if os.environ.get("SESSION_SECRET_KEY"):
        configure_session_middleware(app)
    configure_cors_middleware(app)
    configure_apitally_middleware(app)
    configure_lazy_admin(app)
    return app
