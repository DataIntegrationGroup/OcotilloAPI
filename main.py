import os

import sentry_sdk
from dotenv import load_dotenv

from core.initializers import register_routes

load_dotenv()

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
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
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not SESSION_SECRET_KEY:
    # Fallback primarily for local development; production should set the env var.
    SESSION_SECRET_KEY = "dev-session-secret-key"
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
