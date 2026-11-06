"""rename permission_history to site_activity_consent

Revision ID: 652b0abb3241
Revises: c89d6680bff6
Create Date: 2026-11-02 00:00:00.000000

ADR5 splits two things the schema called "permission": what staff are allowed
to do (permission_grant, c89d6680bff6) and what an owner allows at their site.
This table is the second, so it is renamed to say so, and its columns follow:

    permission_history                 -> site_activity_consent
    permission_type                    -> activity
    permission_allowed                 -> allowed

Written by hand. Autogenerate reads a renamed model as one table dropped and
another created, which would delete every consent on record.

The Postgres default names for the sequence and constraints are renamed too,
as is ix_permission_history_target_type_start. That index is created by raw
SQL in e1f2a3b4c5d6 and is not declared on the model, so it is renamed IF
EXISTS: a database built from model metadata does not have it.

Constraints are renamed from the catalog rather than from a fixed list.
PostgreSQL 18 records NOT NULL constraints in pg_constraint under generated
names (permission_history_contact_id_not_null and seven more); 17, which
staging runs, does not. Reading the names at run time covers both, and covers
the primary key and the three foreign keys from 66ac1af4ba69, which predates
any naming convention in db/base.py.

ogc_internal_water_well_field_operations reads this table. Postgres binds a
view to the table's OID and its columns' attnums, so the view follows the
rename and is not rebuilt here; its published columns are all aliased
(may_measure_water_level and the rest) and do not change. The view SQL copied
through e1f2a3b4c5d6, f2a3b4c5d6e7 and a3b4c5d6e7f8 still says
permission_history, permission_type and permission_allowed, which is correct
for those revisions and must stay. The next migration that rebuilds the view
from that SQL has to use the new names, or it fails with "relation does not
exist".

Each direction ends with a guard that fails if any constraint, index, sequence
or column on the table still carries the old vocabulary, so an object this
migration does not know about stops the upgrade instead of keeping a stale
name.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "652b0abb3241"
down_revision: Union[str, Sequence[str], None] = "c89d6680bff6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TABLE = "permission_history"
NEW_TABLE = "site_activity_consent"

# (old, new)
COLUMNS = [
    ("permission_type", "activity"),
    ("permission_allowed", "allowed"),
]
SEQUENCE = ("permission_history_id_seq", "site_activity_consent_id_seq")
INDEXES = [
    (
        "ix_permission_history_target_type_start",
        "ix_site_activity_consent_target_activity_start",
    ),
]


def _rename_constraints(table: str, old_prefix: str, new_prefix: str) -> None:
    """Rename every constraint on `table` named `<old_prefix>_...`.

    The table prefix is swapped, and a column name that follows it is mapped
    through COLUMNS, so permission_history_permission_type_fkey becomes
    site_activity_consent_activity_fkey. Renaming the primary key constraint
    also renames its index.
    """
    if old_prefix == OLD_TABLE:
        column_map = COLUMNS
    else:
        column_map = [(new, old) for old, new in COLUMNS]
    column_rewrites = "\n".join(
        f"                new_name := regexp_replace(new_name, "
        f"'^{new_prefix}_{old_col}_', '{new_prefix}_{new_col}_');"
        for old_col, new_col in column_map
    )
    op.execute(f"""
        DO $$
        DECLARE
            r record;
            new_name text;
        BEGIN
            FOR r IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = '{table}'::regclass
                  AND starts_with(conname, '{old_prefix}_')
            LOOP
                new_name := '{new_prefix}_'
                    || substr(r.conname, length('{old_prefix}_') + 1);
{column_rewrites}
                EXECUTE format(
                    'ALTER TABLE {table} RENAME CONSTRAINT %I TO %I',
                    r.conname,
                    new_name
                );
            END LOOP;
        END
        $$
        """)


def _assert_no_names_containing(table: str, fragments: list[str]) -> None:
    """Raise if any constraint, index, sequence or column on `table` still
    contains one of `fragments`."""
    patterns = ", ".join(f"'%{f}%'" for f in fragments)
    op.execute(f"""
        DO $$
        DECLARE
            leftovers text;
        BEGIN
            SELECT string_agg(name, ', ' ORDER BY name) INTO leftovers
            FROM (
                SELECT conname::text AS name
                FROM pg_constraint
                WHERE conrelid = '{table}'::regclass
                UNION ALL
                SELECT indexrelid::regclass::text
                FROM pg_index
                WHERE indrelid = '{table}'::regclass
                UNION ALL
                SELECT attname::text
                FROM pg_attribute
                WHERE attrelid = '{table}'::regclass
                  AND attnum > 0
                  AND NOT attisdropped
                UNION ALL
                SELECT d.objid::regclass::text
                FROM pg_depend AS d
                JOIN pg_class AS s ON s.oid = d.objid AND s.relkind = 'S'
                WHERE d.refobjid = '{table}'::regclass
            ) AS names
            WHERE name LIKE ANY (ARRAY[{patterns}]);

            IF leftovers IS NOT NULL THEN
                RAISE EXCEPTION
                    '{table} still has objects with the old names: %', leftovers;
            END IF;
        END
        $$
        """)


def upgrade() -> None:
    op.rename_table(OLD_TABLE, NEW_TABLE)
    for old, new in COLUMNS:
        op.alter_column(NEW_TABLE, old, new_column_name=new)
    op.execute(f"ALTER SEQUENCE {SEQUENCE[0]} RENAME TO {SEQUENCE[1]}")
    _rename_constraints(NEW_TABLE, OLD_TABLE, NEW_TABLE)
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX IF EXISTS {old} RENAME TO {new}")

    _assert_no_names_containing(NEW_TABLE, ["permission"])


def downgrade() -> None:
    for old, new in INDEXES:
        op.execute(f"ALTER INDEX IF EXISTS {new} RENAME TO {old}")
    _rename_constraints(NEW_TABLE, NEW_TABLE, OLD_TABLE)
    op.execute(f"ALTER SEQUENCE {SEQUENCE[1]} RENAME TO {SEQUENCE[0]}")
    for old, new in COLUMNS:
        op.alter_column(NEW_TABLE, new, new_column_name=old)
    op.rename_table(NEW_TABLE, OLD_TABLE)

    # "activity" also catches site_activity_*; "allowed" cannot be checked
    # this way because the old column name, permission_allowed, contains it.
    _assert_no_names_containing(OLD_TABLE, ["activity"])
