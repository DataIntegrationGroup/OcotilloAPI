"""expand actively_monitored_wells to all groups

Drops the "WHERE group name = 'water level network'" restriction so the view
covers currently-monitored wells in any group, not just one. Public view
adds a group release_status = 'public' check instead, so draft/private
groups don't leak through now that any group can show up. A well in
multiple groups is aggregated into one row (group_ids/group_names/group_types
as arrays) rather than one row per group, so `id` stays unique -- pygeoapi's
id_field: id assumes exactly one row per id for /items/{id} lookups.

Revision ID: 986e0eb85ab3
Revises: c3d4e5f6a7b8
Create Date: 2026-08-20 10:55:25.697907

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "986e0eb85ab3"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_view_or_materialized_view(view_name: str) -> None:
    # DROP VIEW IF EXISTS / DROP MATERIALIZED VIEW IF EXISTS only suppress
    # "relation does not exist" -- Postgres still raises WrongObjectType if
    # the relation exists as the other kind, so the relation's actual kind
    # must be checked first rather than trying both blindly.
    bind = op.get_bind()
    relkind = bind.execute(
        text("SELECT relkind FROM pg_class WHERE oid = to_regclass(:name)"),
        {"name": view_name},
    ).scalar()
    if relkind == "m":
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
    elif relkind == "v":
        op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))


def _create_actively_monitored_wells_view(all_groups: bool) -> str:
    if all_groups:
        # Aggregated: one row per well, group_ids/group_names/group_types as
        # arrays, so `id` stays unique even when a well belongs to several
        # groups. release_status = 'public' is checked on the group row
        # itself (mirrors _create_project_areas_view's public_only handling)
        # since any group can appear here now, not just one hardcoded one.
        # group_thing_association has no unique constraint on
        # (group_id, thing_id), so distinct_memberships de-dupes before
        # aggregating; all three arrays are ordered by the same group_id key
        # so they stay index-aligned with each other (ordering each array by
        # its own column, e.g. names alphabetically, would desync them).
        return """
            CREATE VIEW ogc_actively_monitored_wells AS
            WITH latest_monitoring_status AS (
                SELECT DISTINCT ON (sh.target_id)
                    sh.target_id AS thing_id,
                    sh.status_value
                FROM status_history AS sh
                WHERE
                    sh.target_table = 'thing'
                    AND sh.status_type = 'Monitoring Status'
                ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
            ),
            distinct_memberships AS (
                SELECT DISTINCT
                    gta.thing_id,
                    g.id AS group_id,
                    g.name AS group_name,
                    g.group_type
                FROM group_thing_association AS gta
                JOIN "group" AS g ON g.id = gta.group_id
                WHERE g.release_status = 'public'
            )
            SELECT
                wws.id,
                wws.name,
                'water well'::text AS thing_type,
                wws.well_depth,
                wws.elevation,
                wws.elevation_method,
                wws.formation_zone,
                wws.total_water_levels,
                wws.last_water_level,
                wws.last_water_level_datetime,
                wws.min_water_level,
                wws.max_water_level,
                wws.water_level_trend_ft_per_year,
                array_agg(dm.group_id ORDER BY dm.group_id) AS group_ids,
                array_agg(dm.group_name ORDER BY dm.group_id) AS group_names,
                array_agg(dm.group_type ORDER BY dm.group_id) AS group_types,
                wws.point
            FROM ogc_water_well_summary AS wws
            JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
            JOIN distinct_memberships AS dm ON dm.thing_id = wws.id
            WHERE lms.status_value = 'Currently monitored'
            GROUP BY
                wws.id, wws.name, wws.well_depth, wws.elevation,
                wws.elevation_method, wws.formation_zone,
                wws.total_water_levels, wws.last_water_level,
                wws.last_water_level_datetime, wws.min_water_level,
                wws.max_water_level, wws.water_level_trend_ft_per_year,
                wws.point
        """
    # Historical (downgrade target): byte-for-byte the pre-fix view, single
    # group_id/group_name/group_type columns, scoped to one hardcoded group.
    return """
        CREATE VIEW ogc_actively_monitored_wells AS
        WITH latest_monitoring_status AS (
            SELECT DISTINCT ON (sh.target_id)
                sh.target_id AS thing_id,
                sh.status_value
            FROM status_history AS sh
            WHERE
                sh.target_table = 'thing'
                AND sh.status_type = 'Monitoring Status'
            ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
        )
        SELECT
            wws.id,
            wws.name,
            'water well'::text AS thing_type,
            wws.well_depth,
            wws.elevation,
            wws.elevation_method,
            wws.formation_zone,
            wws.total_water_levels,
            wws.last_water_level,
            wws.last_water_level_datetime,
            wws.min_water_level,
            wws.max_water_level,
            wws.water_level_trend_ft_per_year,
            g.id AS group_id,
            g.name AS group_name,
            g.group_type,
            wws.point
        FROM "group" AS g
        JOIN group_thing_association AS gta ON gta.group_id = g.id
        JOIN ogc_water_well_summary AS wws ON wws.id = gta.thing_id
        JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
        WHERE lower(trim(g.name)) = 'water level network'
          AND lms.status_value = 'Currently monitored'
    """


def _create_internal_actively_monitored_wells_view(all_groups: bool) -> str:
    if all_groups:
        # Aggregated, same shape as the public view's all_groups branch, but
        # no release_status filter -- the internal mount is unfiltered by
        # design, same as its sibling views. See the public branch's comment
        # for why distinct_memberships + a shared ORDER BY key is needed.
        return """
            CREATE VIEW ogc_internal_actively_monitored_wells AS
            WITH latest_monitoring_status AS (
                SELECT DISTINCT ON (sh.target_id)
                    sh.target_id AS thing_id,
                    sh.status_value
                FROM status_history AS sh
                WHERE
                    sh.target_table = 'thing'
                    AND sh.status_type = 'Monitoring Status'
                ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
            ),
            distinct_memberships AS (
                SELECT DISTINCT
                    gta.thing_id,
                    g.id AS group_id,
                    g.name AS group_name,
                    g.group_type
                FROM group_thing_association AS gta
                JOIN "group" AS g ON g.id = gta.group_id
            )
            SELECT
                wws.id,
                wws.name,
                'water well'::text AS thing_type,
                wws.well_depth,
                wws.elevation,
                wws.elevation_method,
                wws.formation_zone,
                wws.total_water_levels,
                wws.last_water_level,
                wws.last_water_level_datetime,
                wws.min_water_level,
                wws.max_water_level,
                wws.water_level_trend_ft_per_year,
                array_agg(dm.group_id ORDER BY dm.group_id) AS group_ids,
                array_agg(dm.group_name ORDER BY dm.group_id) AS group_names,
                array_agg(dm.group_type ORDER BY dm.group_id) AS group_types,
                wws.point
            FROM ogc_internal_water_well_summary AS wws
            JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
            JOIN distinct_memberships AS dm ON dm.thing_id = wws.id
            WHERE lms.status_value = 'Currently monitored'
            GROUP BY
                wws.id, wws.name, wws.well_depth, wws.elevation,
                wws.elevation_method, wws.formation_zone,
                wws.total_water_levels, wws.last_water_level,
                wws.last_water_level_datetime, wws.min_water_level,
                wws.max_water_level, wws.water_level_trend_ft_per_year,
                wws.point
        """
    # Historical (downgrade target): byte-for-byte the pre-fix view.
    return """
        CREATE VIEW ogc_internal_actively_monitored_wells AS
        WITH latest_monitoring_status AS (
            SELECT DISTINCT ON (sh.target_id)
                sh.target_id AS thing_id,
                sh.status_value
            FROM status_history AS sh
            WHERE
                sh.target_table = 'thing'
                AND sh.status_type = 'Monitoring Status'
            ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
        )
        SELECT
            wws.id,
            wws.name,
            'water well'::text AS thing_type,
            wws.well_depth,
            wws.elevation,
            wws.elevation_method,
            wws.formation_zone,
            wws.total_water_levels,
            wws.last_water_level,
            wws.last_water_level_datetime,
            wws.min_water_level,
            wws.max_water_level,
            wws.water_level_trend_ft_per_year,
            g.id AS group_id,
            g.name AS group_name,
            g.group_type,
            wws.point
        FROM "group" AS g
        JOIN group_thing_association AS gta ON gta.group_id = g.id
        JOIN ogc_internal_water_well_summary AS wws ON wws.id = gta.thing_id
        JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
        WHERE lower(trim(g.name)) = 'water level network'
          AND lms.status_value = 'Currently monitored'
    """


def upgrade() -> None:
    """Upgrade schema."""
    _drop_view_or_materialized_view("ogc_actively_monitored_wells")
    op.execute(text(_create_actively_monitored_wells_view(all_groups=True)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_actively_monitored_wells IS "
            "'Actively (currently) monitored wells across all groups for pygeoapi.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_actively_monitored_wells")
    op.execute(text(_create_internal_actively_monitored_wells_view(all_groups=True)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_actively_monitored_wells IS "
            "'Actively (currently) monitored wells across all groups, "
            "for the internal pygeoapi mount.'"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    _drop_view_or_materialized_view("ogc_actively_monitored_wells")
    op.execute(text(_create_actively_monitored_wells_view(all_groups=False)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_actively_monitored_wells IS "
            "'Wells in the Water Level Network group for pygeoapi.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_actively_monitored_wells")
    op.execute(text(_create_internal_actively_monitored_wells_view(all_groups=False)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_actively_monitored_wells IS "
            "'Unfiltered wells in the Water Level Network group, "
            "for the internal pygeoapi mount.'"
        )
    )
