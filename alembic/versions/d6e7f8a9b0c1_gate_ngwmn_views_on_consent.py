"""Gate the NGWMN views on landowner consent

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-03

c5d6e7f8a9b0 put the public-web destination under consent. This does the same
for `ngwmn`, the harvester destination, and generalizes the SQL helper so a
third destination needs no new function.

**Rows, not columns, and why that is the same rule.** The public wells layer
carries several data types in one row, so consent for one and not another is
expressed by nulling columns. Each NGWMN view is a single data type reported
against `PointID`, which is the well's name -- site metadata. Nulling that
leaves a row NGWMN cannot match to a well, so the rule "null what is not
consented, and drop a row whose identity would be null" removes the row
outright here. One policy, two shapes, decided by the shape of the layer.

Each view therefore requires two consents: `site metadata` for the identity it
reports against, and the type it carries --

* `NGWMN_WellConstruction` -- well construction. Casing and screen detail.
* `NGWMN_WaterLevels` -- water level. Depth-to-water readings.
* `NGWMN_Lithology` -- well construction. A borehole log is completion detail
  by the lexicon's reading; it is not its own access data type today.

**Not a narrowing, in practice.** The legacy seed wrote consent against
`ngwmn` for every thing that was `release_status='public'`, so the wells NGWMN
harvests today keep flowing. What changes is that a revocation now stops one.

**The lag.** These three are plain views, so a revocation lands on the next
harvest. The six materialized public collections refresh at 09:00 UTC and lag
by up to a day -- never early. Documented in c5d6e7f8a9b0 and
docs/data-embargo.md rather than fixed here.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# One function for every destination. `public_web_consent_types` becomes a
# wrapper rather than a second copy: the date rule -- started, not ended, not
# revoked, matching domain.access.is_active -- belongs in one place even in
# SQL.
GENERAL_FUNCTION = """
CREATE OR REPLACE FUNCTION destination_consent_types(
    target_thing_id integer,
    destination_slug text
)
RETURNS text[]
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(array_agg(DISTINCT pc.data_type), ARRAY[]::text[])
    FROM publication_consent pc
    JOIN destination d ON d.id = pc.destination_id
    WHERE pc.thing_id = target_thing_id
      AND d.slug = destination_slug
      AND d.active
      AND pc.revoked_at IS NULL
      AND pc.starts_at <= current_date
      AND (pc.ends_at IS NULL OR pc.ends_at >= current_date)
$$;

CREATE OR REPLACE FUNCTION public_web_consent_types(target_thing_id integer)
RETURNS text[]
LANGUAGE sql
STABLE
AS $$
    SELECT destination_consent_types(target_thing_id, 'public-web')
$$;
"""

# The predicate appended to each view's WHERE clause. `t` is the thing in all
# three definitions below.
CONSENT_PREDICATE = """
    AND 'site metadata' = ANY(destination_consent_types(t.id, 'ngwmn'))
    AND '{data_type}' = ANY(destination_consent_types(t.id, 'ngwmn'))
"""

WELL_CONSTRUCTION = """
 SELECT t.name AS "PointID",
        CASE
            WHEN t.well_casing_depth IS NOT NULL THEN 0::double precision
            ELSE NULL::double precision
        END AS "CasingTop",
    t.well_casing_depth AS "CasingBottom",
        CASE
            WHEN t.well_casing_depth IS NOT NULL THEN 'ft bgs'::text
            ELSE NULL::text
        END AS "CasingDepthUnits",
    ws.screen_depth_top AS "ScreenTop",
    ws.screen_depth_bottom AS "ScreenBottom",
        CASE
            WHEN ws.screen_depth_bottom IS NOT NULL THEN 'ft bgs'::text
            ELSE NULL::text
        END AS "ScreenBottomUnit",
    ws.screen_description AS "ScreenDescription",
    cm.materials AS "CasingDescription"
   FROM thing t
     LEFT JOIN well_screen ws ON ws.thing_id = t.id
     LEFT JOIN LATERAL ( SELECT string_agg(wcm.material::text, ', '::text ORDER BY (wcm.material::text)) AS materials
           FROM well_casing_material wcm
          WHERE wcm.thing_id = t.id) cm ON true
  WHERE t.thing_type::text = 'water well'::text AND t.release_status::text = 'public'::text
"""

WATER_LEVELS = """
 SELECT t.name AS "PointID",
        CASE
            WHEN (o.observation_datetime AT TIME ZONE 'UTC'::text)::time without time zone = '00:00:00'::time without time zone THEN (o.observation_datetime AT TIME ZONE 'UTC'::text)::date
            ELSE (o.observation_datetime AT TIME ZONE 'America/Denver'::text)::date
        END AS "DateMeasured",
    o.value - COALESCE(o.measuring_point_height, 0::double precision) AS "DepthToWaterBGS",
    'ft bgs'::text AS "WLUnits",
        CASE s.sample_method
            WHEN 'Steel-tape measurement'::text THEN 'Steel tape'::text
            WHEN 'Electric tape measurement (E-probe)'::text THEN 'Electric tape'::text
            WHEN 'Observed (required for F, N, and W water level status)'::text THEN 'Acoustic Sounder'::text
            WHEN 'Estimated'::text THEN 'Estimated'::text
            WHEN 'Reported, method not known'::text THEN 'Reported'::text
            WHEN 'Pressure-gage measurement'::text THEN 'Pressure gauge'::text
            WHEN 'Unknown (for legacy data only; not for new data entry)'::text THEN 'Unknown; from legacy data'::text
            ELSE NULL::text
        END AS "MeasurementMethod",
        CASE o.nma_data_quality
            WHEN 'Water level accurate to within two hundreths of a foot'::text THEN '0.02 ft'::text
            WHEN 'Water level accurate to within one foot'::text THEN '1.0 ft'::text
            WHEN 'Water level accuracy not to nearest foot or water level not repeatable'::text THEN 'Unknown'::text
            ELSE NULL::text
        END AS "WLAccuracy",
    true AS "PublicRelease"
   FROM observation o
     JOIN sample s ON s.id = o.sample_id
     JOIN field_activity fa ON fa.id = s.field_activity_id
     JOIN field_event fe ON fe.id = fa.field_event_id
     JOIN thing t ON t.id = fe.thing_id
     JOIN parameter p ON p.id = o.parameter_id
  WHERE p.parameter_name::text = 'groundwater level'::text AND o.release_status::text = 'public'::text AND s.release_status::text = 'public'::text AND fa.release_status::text = 'public'::text AND fe.release_status::text = 'public'::text AND t.release_status::text = 'public'::text
"""

LITHOLOGY = """
 SELECT tgfa.id AS "OBJECTID",
    t.name AS "PointID",
    gf.lithology AS "Lithology",
    gf.lithology AS "TERM",
    NULL::character varying AS "StratSource",
    tgfa.top_depth AS "StratTop",
        CASE
            WHEN tgfa.top_depth IS NOT NULL THEN 'ft bgs'::text
            ELSE NULL::text
        END AS "StratTopUnit",
    tgfa.bottom_depth AS "StratBottom",
        CASE
            WHEN tgfa.bottom_depth IS NOT NULL THEN 'ft bgs'::text
            ELSE NULL::text
        END AS "StratBottomUnit"
   FROM thing_geologic_formation_association tgfa
     JOIN thing t ON t.id = tgfa.thing_id
     JOIN geologic_formation gf ON gf.id = tgfa.geologic_formation_id
  WHERE gf.lithology IS NOT NULL AND t.release_status::text = 'public'::text
"""

VIEWS = [
    ("NGWMN_WellConstruction", WELL_CONSTRUCTION, "well construction"),
    ("NGWMN_WaterLevels", WATER_LEVELS, "water level"),
    ("NGWMN_Lithology", LITHOLOGY, "well construction"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(GENERAL_FUNCTION)
    for name, body, data_type in VIEWS:
        predicate = CONSENT_PREDICATE.format(data_type=data_type)
        op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {body}{predicate};')


def downgrade() -> None:
    """Downgrade schema."""
    for name, body, _ in VIEWS:
        op.execute(f'CREATE OR REPLACE VIEW "{name}" AS {body};')
    op.execute("DROP FUNCTION IF EXISTS destination_consent_types(integer, text);")
