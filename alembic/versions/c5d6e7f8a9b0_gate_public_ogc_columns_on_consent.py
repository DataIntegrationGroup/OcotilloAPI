"""Gate public OGC columns on landowner consent

Revision ID: c5d6e7f8a9b0
Revises: 8f0be6a2b61c
Create Date: 2026-09-03

The public OGC collections decide what they publish from `release_status`, a
column set in bulk. `publication_consent` decides it per (thing, destination,
data type), which is what a landowner actually agreed to. Until now the second
governed nothing a member of the public could fetch (ADR5, A.6).

This is the public-web destination coming under consent, one layer first.

**Columns are nulled, not rows dropped.** A collection's column set spans
several data types -- the wells layer carries site metadata and well
construction together -- so consent for one and not the other has to be
expressible within a fixed tabular schema. Absence is not, per row; null is.
That differs deliberately from the internal read path, where a withheld field
is absent rather than null, because there a payload is a dict and can simply
not have the key. Same policy, two shapes, because the media differ.

**Geometry follows site metadata**, which means a well consented for well
construction only publishes a feature with no geometry. That is the honest
reading of the consent, and it is worth knowing that such a feature is not
renderable on a map.

**The lag.** This layer is a plain view, so a revocation lands on the next
request. Six of the public collections are materialized views refreshed by one
pg_cron job at 09:00 UTC, and for those a revocation will land up to a day
late -- never early. That is the same granularity the embargo work accepted
for release dates (see docs/data-embargo.md), and it is a documented departure
from the immediacy `domain/access.py` promises. Recorded here rather than
fixed here.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "a396d7d9928d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The consent a thing carries for the public web, today. STABLE rather than
# IMMUTABLE: it reads tables, and a matview refresh must see the current
# answer. The date comparison is the same rule as domain.access.is_active --
# started, not ended, not revoked -- and it lives here as well as there
# because a view cannot call Python. The test suite asserts the two agree.
CONSENT_FUNCTION = """
CREATE OR REPLACE FUNCTION public_web_consent_types(target_thing_id integer)
RETURNS text[]
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(array_agg(DISTINCT pc.data_type), ARRAY[]::text[])
    FROM publication_consent pc
    JOIN destination d ON d.id = pc.destination_id
    WHERE pc.thing_id = target_thing_id
      AND d.slug = 'public-web'
      AND d.active
      AND pc.revoked_at IS NULL
      AND pc.starts_at <= current_date
      AND (pc.ends_at IS NULL OR pc.ends_at >= current_date)
$$;
"""

# Which data type each published column belongs to, from
# core/data-type-fields.yml. Restated here because a view cannot read the YAML,
# and asserted equal to it by tests/test_ogc_consent.py -- two copies of a
# security baseline is how the two drift.
# (column, data type, declared SQL type). The cast is load-bearing: CASE
# returns an unqualified varchar, and CREATE OR REPLACE VIEW refuses a column
# whose type changed -- including losing a length modifier.
WATER_WELLS_COLUMNS = [
    ("id", None, None),
    ("name", "site metadata", "character varying"),
    ("first_visit_date", "site metadata", "date"),
    # Derived from observations rather than stored, and it is a fact about the
    # readings: when this well was last measured.
    ("last_observation_date", "water level", "date"),
    # Published by the view, filtered out by the OGC never-public list.
    ("nma_pk_welldata", None, None),
    ("well_depth", "well construction", "double precision"),
    ("hole_depth", "well construction", "double precision"),
    ("well_casing_diameter", "well construction", "double precision"),
    ("well_casing_depth", "well construction", "double precision"),
    ("well_completion_date", "well construction", "date"),
    ("well_driller_name", "well construction", "character varying(200)"),
    ("well_construction_method", "well construction", "character varying(100)"),
    ("well_pump_type", "well construction", "character varying(100)"),
    ("well_pump_depth", "well construction", "double precision"),
    ("formation_completion_code", "well construction", "character varying(100)"),
    ("nma_formation_zone", "well construction", "character varying(25)"),
    ("release_status", None, None),
    ("elevation", "site metadata", "double precision"),
    ("point", "site metadata", "geometry(Point,4326)"),
]

ORIGINAL_WATER_WELLS = """
 WITH latest_location AS (
         SELECT DISTINCT ON (lta.thing_id) lta.thing_id,
            lta.location_id,
            lta.effective_start
           FROM location_thing_association lta
          WHERE lta.effective_end IS NULL
          ORDER BY lta.thing_id, lta.effective_start DESC
        )
 SELECT t.id,
    t.name,
    t.first_visit_date,
    (last_obs.last_observation_datetime AT TIME ZONE 'UTC'::text)::date AS last_observation_date,
    t.nma_pk_welldata,
    t.well_depth,
    t.hole_depth,
    t.well_casing_diameter,
    t.well_casing_depth,
    t.well_completion_date,
    t.well_driller_name,
    t.well_construction_method,
    t.well_pump_type,
    t.well_pump_depth,
    t.formation_completion_code,
    t.nma_formation_zone,
    t.release_status,
    l.elevation,
    l.point
   FROM thing t
     JOIN latest_location ll ON ll.thing_id = t.id
     JOIN location l ON l.id = ll.location_id
     LEFT JOIN LATERAL ( SELECT max(o.observation_datetime) AS last_observation_datetime
           FROM observation o
             JOIN sample s ON s.id = o.sample_id
             JOIN field_activity fa ON fa.id = s.field_activity_id
             JOIN field_event fe ON fe.id = fa.field_event_id
          WHERE fe.thing_id = t.id AND o.release_status::text = 'public'::text) last_obs ON true
  WHERE t.thing_type::text = 'water well'::text AND t.release_status::text = 'public'::text
"""


def _projected_columns() -> str:
    """Each column, wrapped in the consent its data type requires.

    A column belonging to no data type -- the key, the release state -- passes
    through: `always` is not grantable and so is not consentable either.
    """
    parts = []
    for column, data_type, sql_type in WATER_WELLS_COLUMNS:
        if data_type is None:
            parts.append(f"    base.{column}")
        else:
            parts.append(
                f"    (CASE WHEN '{data_type}' = ANY(consent.types)\n"
                f"          THEN base.{column} END)::{sql_type} AS {column}"
            )
    return ",\n".join(parts)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(CONSENT_FUNCTION)
    op.execute(
        f"""
        CREATE OR REPLACE VIEW ogc_water_wells AS
        SELECT
{_projected_columns()}
        FROM ({ORIGINAL_WATER_WELLS}) base
        LEFT JOIN LATERAL (
            SELECT public_web_consent_types(base.id) AS types
        ) consent ON TRUE;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"CREATE OR REPLACE VIEW ogc_water_wells AS {ORIGINAL_WATER_WELLS};")
    op.execute("DROP FUNCTION IF EXISTS public_web_consent_types(integer);")
