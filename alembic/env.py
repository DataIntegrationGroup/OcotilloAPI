from alembic import context
from dotenv import load_dotenv
from logging.config import fileConfig
from os import environ
from sqlalchemy import engine_from_config
from sqlalchemy import pool


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel

# from db import Base  # Import your Base from models/__init__.py
from db import Base

# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

load_dotenv()

user = environ.get("POSTGRES_USER", None)
password = environ.get("POSTGRES_PASSWORD", None)
db = environ.get("POSTGRES_DB", None)
host = environ.get("POSTGRES_HOST", None)
port = environ.get("POSTGRES_PORT", None)

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
config.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)


def include_object(object, name, type_, reflected, compare_to):
    # List of tables to exclude from Alembic autogenerate
    # these tables are created by PostGIS and TIGER geocoder
    # and should not be included in migration upgrades or downgrades
    excluded_tables = {
        "loader_lookuptables",
        "addr",
        "county",
        "featnames",
        "state_lookup",
        "place_lookup",
        "zip_state",
        "secondary_unit_lookup",
        "state",
        "addrfeat",
        "direction_lookup",
        "faces",
        "bg",
        "zip_lookup_all",
        "cousub",
        "pagc_rules",
        "zcta5",
        "zip_lookup",
        "county_lookup",
        "edges",
        "tabblock20",
        "loader_variables",
        "pagc_gaz",
        "street_type_lookup",
        "geocode_settings_default",
        "geocode_settings",
        "zip_state_loc",
        "tract",
        "tabblock",
        "spatial_ref_sys",
        "topology",
        "pagc_lex",
        "loader_platform",
        "zip_lookup_base",
        "place",
        "countysub_lookup",
        "layer",
    }
    if type_ == "table" and name in excluded_tables:
        return False
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
