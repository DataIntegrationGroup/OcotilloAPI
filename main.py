import os

from dotenv import load_dotenv

from core.initializers import configure_admin, configure_middleware, register_routes

load_dotenv()
DSN = os.environ.get("SENTRY_DSN")

if DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=DSN,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
        # Set profile_lifecycle to "trace" to automatically
        # run the profiler on when there is an active transaction
        profile_lifecycle="trace",
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )


def create_app():
    from core.app import app as core_app

    register_routes(core_app)
    configure_middleware(core_app)
    configure_admin(core_app)
    return core_app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
