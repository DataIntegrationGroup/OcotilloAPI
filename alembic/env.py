import copy
import logging
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, engine_from_config, event, pool, text
from sqlalchemy.engine import URL

from db import Base
from db.initialization import grant_app_read_members
from services.env import get_bool_env

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
alembic_logger = logging.getLogger("alembic.env")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None and os.environ.get(
    "ALEMBIC_USE_FILE_CONFIG", "0"
) not in {"0", "false", "False"}:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
else:
    root_logger = logging.getLogger()
    alembic_logger = logging.getLogger("alembic")
    alembic_logger.handlers = root_logger.handlers[:]
    alembic_logger.setLevel(root_logger.level)
    alembic_logger.propagate = False

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel

# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
model_tables = set(target_metadata.tables.keys())

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

load_dotenv()


def build_database_url():
    """
    Build a SQLAlchemy URL based on driver/env vars.
    For cloudsql we return a psycopg2 URL that targets the mounted Cloud SQL
    Unix socket.
    """
    db_driver = os.environ.get("DB_DRIVER", "").lower()
    if db_driver == "cloudsql":
        user = os.environ.get("CLOUD_SQL_USER", "")
        database = os.environ.get("CLOUD_SQL_DATABASE", "")
        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
        socket_dir = os.environ.get("CLOUD_SQL_SOCKET_DIR", "/cloudsql")
        socket_dir = socket_dir.rstrip("/")
        instance_name = os.environ.get("CLOUD_SQL_INSTANCE_NAME", "")
        password = None
        if not use_iam_auth:
            password = os.environ.get("CLOUD_SQL_PASSWORD", "")
        return URL.create(
            "postgresql+psycopg2",
            username=user,
            password=password,
            database=database,
            query={"host": f"{socket_dir}/{instance_name}"},
        ).render_as_string(hide_password=False)

    # Default/Postgres
    user = os.environ.get("POSTGRES_USER", "")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", 5432)
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


url = build_database_url()
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))


def include_object(object, name, type_, reflected, compare_to):
    # only include tables in sql alchemy model, not auto-generated tables from
    # PostGIS or TIGER
    # Handle None names for unnamed constraints
    if name is None:
        return True
    if type_ == "table" or name.endswith("_version") or name == "transaction":
        return name in model_tables
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_driver = os.environ.get("DB_DRIVER", "").lower()

    if db_driver == "cloudsql":
        from google.auth import default
        from google.auth.transport.requests import Request

        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)

        def get_iam_login_token() -> str:
            scopes = ["https://www.googleapis.com/auth/sqlservice.login"]
            creds, _ = default()
            if hasattr(creds, "with_scopes"):
                creds = creds.with_scopes(scopes=scopes)
            else:
                creds = copy.copy(creds)
                creds._scopes = scopes  # type: ignore[attr-defined]
            creds.refresh(Request())
            if not getattr(creds, "token", None):
                raise RuntimeError("Unable to acquire IAM DB auth token.")
            return creds.token

        connectable = create_engine(
            build_database_url(),
            pool_pre_ping=True,
            poolclass=pool.NullPool,
        )
        if use_iam_auth:

            @event.listens_for(connectable, "do_connect")
            def inject_iam_token(dialect, conn_rec, cargs, cparams):
                cparams["password"] = get_iam_login_token()

    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as role_connection:
        autocommit_role = role_connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        role_exists = autocommit_role.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'app_read'")
        ).first()
        if not role_exists:
            autocommit_role.execute(text("CREATE ROLE app_read"))
        grant_app_read_members(autocommit_role)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

    completion_message = "Alembic migrations completed; " "applying app_read grants"
    alembic_logger.info(completion_message)
    with connectable.connect() as grant_connection:
        autocommit_grants = grant_connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        autocommit_grants.execute(
            text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_read")
        )
        autocommit_grants.execute(
            text(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT ON TABLES TO app_read"
            )
        )
    alembic_logger.info("Applied app_read grants")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
