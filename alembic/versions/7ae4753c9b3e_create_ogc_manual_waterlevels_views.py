"""create ogc_manual_waterlevels and its internal mirror

Backs the ``manual_waterlevels`` OGC API - EDR collection
(``docs/ogc-waterlevels-data-contract.md``), served by
``core.edr_provider.StationEDRProvider``. One row per manual groundwater-level
reading, with:

* station columns: ``id``, ``thing_id``, ``name``, ``thing_type``,
  ``longitude``, ``latitude``, ``release_status``;
* the independent axis: ``datetime``;
* parameter columns, named by the collection's ``parameter_columns`` config:
  ``observation_parameter_name/value/unit`` (depth below ground surface, in
  feet: the reading, converted from meters when its unit is ``m``, minus
  ``COALESCE(measuring_point_height, 0)``) and
  ``qualifier_parameter_name/value`` (the groundwater-level reason);
* station properties, repeated on each of the well's readings so /locations
  needs one query: ``ground_surface_elevation`` (+ units, vertical datum),
  ``well_depth`` (+ units), and the jsonb ``geologic_formation`` and
  ``alternate_ids``.

A reading with a null level is still published when it has a reason (R5).

``ogc_manual_waterlevels`` publishes only public readings of public wells,
and only public alternate ids. ``ogc_internal_manual_waterlevels`` is the
same query without those release filters, for the internal pygeoapi mount.

The older ``ogc_waterlevels`` / ``ogc_internal_waterlevels`` views (manual and
transducer readings combined) are left in place.

Revision ID: 7ae4753c9b3e
Revises: 73d27e78571a
Create Date: 2026-11-18 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "7ae4753c9b3e"
down_revision: Union[str, Sequence[str], None] = "73d27e78571a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_VIEW = "ogc_manual_waterlevels"
INTERNAL_VIEW = "ogc_internal_manual_waterlevels"

# A frozen copy of domain.units.METERS_TO_FEET: a migration keeps the
# arithmetic it was written with rather than tracking a moving import.
METERS_TO_FEET = 3.28084


def _create_view(view_name: str, public_only: bool) -> str:
    """CREATE VIEW for the public view, or for the unfiltered internal mirror."""
    # Release filters: the public view needs the reading, the well and each
    # alternate id to be public. The internal mirror drops all three; the
    # "is this a reading" condition below applies to both.
    reading_filter = (
        "o.release_status = 'public' AND t.release_status = 'public' AND"
        if public_only
        else ""
    )
    alternate_id_filter = "WHERE il.release_status = 'public'" if public_only else ""

    return f"""
        CREATE VIEW {view_name} AS
        SELECT
            o.id                                            AS id,

            -- station columns
            t.id                                             AS thing_id,
            t.name                                           AS name,
            t.thing_type                                     AS thing_type,
            ST_X(l.point)                                    AS longitude,
            ST_Y(l.point)                                    AS latitude,

            -- independent axis
            o.observation_datetime                           AS datetime,

            -- parameter columns (parameter_columns in EDR_COLLECTIONS)
            'groundwater level below ground surface'         AS observation_parameter_name,
            -- the reading in feet (measuring_point_height is always feet)
            -- if the unit is meters, convert to feet; if feet, use as is; otherwise NULL
            CASE o.unit
                WHEN 'm' THEN o.value * {METERS_TO_FEET} - COALESCE(o.measuring_point_height, 0)
                WHEN 'ft' THEN o.value - COALESCE(o.measuring_point_height, 0)
                WHEN 'ftbgs' THEN o.value
                ELSE NULL
            END                                              AS observation_value,
            'ft'                                             AS observation_unit,

            -- set qualifier if the unit is not a recognized length unit and the observation has a value
            'groundwater level reason'                       AS qualifier_parameter_name,
            CASE
                WHEN o.value IS NOT NULL AND o.unit NOT IN ('m', 'ft', 'ftbgs')
                    THEN 'Reported unit is not a length unit'
                ELSE o.groundwater_level_reason
            END                                             AS qualifier_value,

            -- station properties, repeated on each of the well's readings
            l.elevation                                      AS ground_surface_elevation,
            'm'                                              AS ground_surface_elevation_units,
            'NAVD88'                                         AS vertical_datum,
            t.well_depth                                     AS well_depth,
            'ft'                                             AS well_depth_units,
            CASE WHEN t.formation_completion_code IS NOT NULL THEN
                jsonb_build_object(
                    'code',        t.formation_completion_code,
                    'description', lt.definition)
            END                                              AS geologic_formation,
            COALESCE(ids.alternate_ids, '[]'::jsonb)         AS alternate_ids,

            o.release_status                                 AS release_status
        FROM observation o
        JOIN parameter p
            ON p.id = o.parameter_id AND p.parameter_name = 'groundwater level'
        JOIN sample sm          ON sm.id = o.sample_id
        JOIN field_activity fa  ON fa.id = sm.field_activity_id
        JOIN field_event fe     ON fe.id = fa.field_event_id
        JOIN thing t            ON t.id = fe.thing_id AND t.thing_type = 'water well'

        -- select the most recent location for the well
        JOIN LATERAL (
             SELECT location_id
             FROM location_thing_association
             WHERE thing_id = t.id AND effective_end IS NULL
             ORDER BY effective_start DESC, location_id DESC
             LIMIT 1
         ) lta ON TRUE
        JOIN location l ON l.id = lta.location_id
        LEFT JOIN lexicon_term lt ON lt.term = t.formation_completion_code
        LEFT JOIN (
            -- aggregated once per well, not once per reading
            SELECT il.thing_id,
                   jsonb_agg(
                       jsonb_build_object(
                           'id',           il.alternate_id,
                           'relation',     il.relation,
                           'organization', il.alternate_organization)
                       ORDER BY il.id) AS alternate_ids
            FROM thing_id_link il
            {alternate_id_filter}
            GROUP BY il.thing_id
        ) ids ON ids.thing_id = t.id
        WHERE {reading_filter}
            -- a null level with a reason is still a reading (R5)
            (o.value IS NOT NULL OR o.groundwater_level_reason IS NOT NULL)
    """


def upgrade() -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {PUBLIC_VIEW}"))
    op.execute(text(_create_view(PUBLIC_VIEW, public_only=True)))
    op.execute(
        text(
            f"COMMENT ON VIEW {PUBLIC_VIEW} IS "
            "'Public manual depth-to-water readings, with station properties, "
            "for the manual_waterlevels EDR collection.'"
        )
    )

    op.execute(text(f"DROP VIEW IF EXISTS {INTERNAL_VIEW}"))
    op.execute(text(_create_view(INTERNAL_VIEW, public_only=False)))
    op.execute(
        text(
            f"COMMENT ON VIEW {INTERNAL_VIEW} IS "
            "'Unfiltered manual depth-to-water readings, with station "
            "properties, for the internal pygeoapi mount.'"
        )
    )


def downgrade() -> None:
    op.execute(text(f"DROP VIEW IF EXISTS {INTERNAL_VIEW}"))
    op.execute(text(f"DROP VIEW IF EXISTS {PUBLIC_VIEW}"))
