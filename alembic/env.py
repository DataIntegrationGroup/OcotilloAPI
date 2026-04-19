import copy
import logging
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, engine_from_config, pool, text

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

# from db import Base  # Import your Base from models/__init__.py
from db import Base  # noqa: E402
from db.initialization import grant_app_read_members  # noqa: E402

# Import AEM models so Alembic autogenerate discovers them.
# These models share the same Base (db.base.Base), so their tables are
# included in target_metadata automatically.
import db.aem  # noqa: E402,F401

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
    For cloudsql we still return a pg8000 URL (hostless) so Alembic can render
    offline migrations; the actual connection uses a Connector creator in
    run_migrations_online.
    """
    db_driver = os.environ.get("DB_DRIVER", "").lower()
    if db_driver == "cloudsql":
        user = os.environ.get("CLOUD_SQL_USER", "")
        password = os.environ.get("CLOUD_SQL_PASSWORD", "")
        database = os.environ.get("CLOUD_SQL_DATABASE", "")
        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
        # Host is provided by connector, so leave blank.
        if use_iam_auth:
            return f"postgresql+pg8000://{user}@/{database}"
        return f"postgresql+pg8000://{user}:{password}@/{database}"

    # Default/Postgres
    user = os.environ.get("POSTGRES_USER", "")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    database_name = os.environ.get("POSTGRES_DB", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", 5432)
    prefix = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/"
    return prefix + database_name


url = build_database_url()
config.set_main_option("sqlalchemy.url", url)


def include_object(object, name, type_, reflected, compare_to):
    # only include tables in sql alchemy model, not auto-generated
    # tables from PostGIS or TIGER
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
        # Use the Cloud SQL Python Connector for direct Cloud SQL access.
        from google.cloud.sql.connector import Connector
        from google.auth import default
        from google.auth.transport.requests import Request

        instance_name = os.environ.get("CLOUD_SQL_INSTANCE_NAME")
        user = os.environ.get("CLOUD_SQL_USER")
        password = os.environ.get("CLOUD_SQL_PASSWORD")
        database = os.environ.get("CLOUD_SQL_DATABASE")
        use_iam_auth = get_bool_env("CLOUD_SQL_IAM_AUTH", False)
        ip_type = os.environ.get("CLOUD_SQL_IP_TYPE", "public")

        connector = Connector()

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

        def getconn():
            connect_kwargs = {
                "user": user,
                "db": database,
                "ip_type": ip_type,
                "enable_iam_auth": use_iam_auth,
            }
            if use_iam_auth:
                connect_kwargs["password"] = get_iam_login_token()
            else:
                connect_kwargs["password"] = password
            return connector.connect(
                instance_name,
                "pg8000",
                **connect_kwargs,
            )

        connectable = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_pre_ping=True,
            poolclass=pool.NullPool,
        )
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

    alembic_logger.info(  # noqa: E501
        "Alembic migrations completed; applying app_read grants"
    )
    with connectable.connect() as grant_connection:
        autocommit_grants = grant_connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        for schema_name in ("public", "stac"):
            schema_exists = autocommit_grants.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = :schema_name"
                ),
                {"schema_name": schema_name},
            ).first()
            if not schema_exists:
                continue
            autocommit_grants.execute(
                text(f'GRANT USAGE ON SCHEMA "{schema_name}" TO app_read')
            )
            autocommit_grants.execute(
                text(
                    f'GRANT SELECT ON ALL TABLES IN SCHEMA "{schema_name}" '
                    "TO app_read"
                )
            )
            autocommit_grants.execute(
                text(
                    f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema_name}" '
                    "GRANT SELECT ON TABLES TO app_read"
                )
            )
    alembic_logger.info("Applied app_read grants")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
