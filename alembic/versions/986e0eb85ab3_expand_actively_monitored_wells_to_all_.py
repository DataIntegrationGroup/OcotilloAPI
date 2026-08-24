"""expand actively_monitored_wells to all groups

Drops the "WHERE group name = 'water level network'" restriction so the view
covers currently-monitored wells in any group, not just one. Public view
adds a group release_status = 'public' check instead, so draft/private
groups don't leak through now that any group can show up. Inner join to
group/group_thing_association is kept as-is (prod has no currently-monitored
well with zero group memberships); wells in multiple groups intentionally
appear once per group, no aggregation.

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
    # The all_groups branch drops the group-name predicate but still needs
    # to keep draft/private groups off the public mount -- unlike the old
    # single-group filter, any group can appear here now, so the group's own
    # release_status has to be checked directly (mirrors
    # _create_project_areas_view's public_only handling).
    group_filter = (
        "g.release_status = 'public'\n          AND "
        if all_groups
        else "lower(trim(g.name)) = 'water level network'\n          AND "
    )
    return f"""
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
        WHERE {group_filter}lms.status_value = 'Currently monitored'
    """


def _create_internal_actively_monitored_wells_view(all_groups: bool) -> str:
    group_filter = (
        ""
        if all_groups
        else "lower(trim(g.name)) = 'water level network'\n          AND "
    )
    return f"""
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
        WHERE {group_filter}lms.status_value = 'Currently monitored'
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
