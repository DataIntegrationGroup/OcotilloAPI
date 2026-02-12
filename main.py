import os

from dotenv import load_dotenv

from core.initializers import register_routes

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


from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from core.app import app

register_routes(app)

# Session middleware is required for the admin auth flow (request.session access).
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise ValueError("SESSION_SECRET_KEY environment variable is not set.")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# ========== Starlette Admin Interface ==========
# Mount admin interface at /admin
# This provides a web-based UI for managing database records (replaces MS Access)
from admin import create_admin

create_admin(app)
# ==============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust as needed for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APITALLY_CLIENT_ID = os.environ.get("APITALLY_CLIENT_ID")
if APITALLY_CLIENT_ID:
    from apitally.fastapi import ApitallyMiddleware

    app.add_middleware(
        ApitallyMiddleware,
        client_id=APITALLY_CLIENT_ID,
        env=os.environ.get("MODE"),  # "production" or "staging"
        # Optionally enable and configure request logging
        enable_request_logging=True,
        log_request_headers=True,
        log_request_body=True,
        log_response_body=True,
        capture_logs=True,
        capture_traces=False,  # requires instrumentation
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
