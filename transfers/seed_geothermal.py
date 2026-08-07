"""Populate the legacy NM_Wells staging mirror with fake geothermal data.

Seeds the geothermal chain so the /thing/geothermal-well endpoint and the OGC
geothermal views (BHT, temperature-depth, heat-flow) all return data:

    NMW_WellHeaders (GthrmExist=1)
      -> NMW_WellLocations        (lat/long/county/state)
      -> NMW_WellRecords
           -> NMW_WellSamples
                -> NMW_GtBhtHeaders -> NMW_GtBhtData   (bottom-hole temps)
                -> NMW_GtTempDepths                    (temp-vs-depth profile)
                -> NMW_GtSumHeatFlow                   (summary heat flow)

TEMPORARY: this seeds the staging mirror, not the Ocotillo `thing` table. Once
the NM_Wells -> Ocotillo transform exists, seed `thing` instead (see seed.py).

Run with:
    docker compose exec -T app python -m transfers.seed_geothermal
"""

import random
import uuid

from faker import Faker
from sqlalchemy import select

from db.engine import session_ctx
from db.nmw_legacy import (
    NMW_GtBhtData,
    NMW_GtBhtHeaders,
    NMW_GtSumHeatFlow,
    NMW_GtTempDepths,
    NMW_WellHeaders,
    NMW_WellLocations,
    NMW_WellRecords,
    NMW_WellSamples,
)

fake = Faker()
Faker.seed(42)
random.seed(42)

# Integer PKs on heap tables (OBJECTID). Base high enough to never collide with
# real dump rows loaded by transfers.nmw_mirror_transfer.
_OID_BASE = 9_000_000

# Rough NM bounding-box anchors (lat, lon), mirrors transfers/seed.py.
NEW_MEXICO_BOUNDS = [
    (36.9, -106.6),  # Taos
    (35.1, -106.6),  # Albuquerque
    (32.3, -106.8),  # Las Cruces
    (34.4, -103.2),  # Clovis
    (36.7, -108.2),  # Farmington
]
COUNTIES = ["Bernalillo", "Santa Fe", "Doña Ana", "Sandoval", "Grant", "Otero"]


def geothermal_data_exists() -> bool:
    with session_ctx() as s:
        return (
            s.scalar(
                select(NMW_WellHeaders.well_data_id)
                .where(NMW_WellHeaders.gthrm_exist == 1)
                .limit(1)
            )
            is not None
        )


def seed_geothermal(n: int = 8, skip_if_exists: bool = True):
    """Seed ~`n` geothermal wells and their child measurements."""
    if skip_if_exists and geothermal_data_exists():
        print("Geothermal data exists; skipping seeding.")
        return

    oid = _OID_BASE

    with session_ctx() as s:
        for i in range(n):
            well_data_id = uuid.uuid4()
            base_lat, base_lon = random.choice(NEW_MEXICO_BOUNDS)
            lat = round(base_lat + random.uniform(-0.3, 0.3), 6)
            lon = round(base_lon + random.uniform(-0.3, 0.3), 6)
            total_depth = round(random.uniform(800, 12000), 1)

            s.add(
                NMW_WellHeaders(
                    well_data_id=well_data_id,
                    api=fake.numerify("30-###-#####"),
                    well_class="Oil & Gas",
                    well_type=random.choice(["Exploration", "Production", "Wildcat"]),
                    well_orient="Vertical",
                    cur_well_nam=f"GEOTHERMAL-{i + 1:04d}",
                    cur_well_num=str(random.randint(1, 30)),
                    cur_status=random.choice(["Active", "Plugged", "Abandoned"]),
                    cur_operatr=fake.company(),
                    cur_owner=fake.company(),
                    total_depth=total_depth,
                    compl_date=fake.date_time_between("-40y", "-1y"),
                    gthrm_exist=1,  # flags this as a geothermal well
                    comments="Seeded geothermal well (fake data).",
                )
            )
            # The mirror columns are plain (no ORM ForeignKey), so SQLAlchemy
            # cannot dependency-order inserts. Flush each parent tier before its
            # children so the DB-level FK constraints (V10) are satisfied.
            s.flush()

            oid += 1
            s.add(
                NMW_WellLocations(
                    object_id=oid,
                    well_data_id=well_data_id,
                    state="NM",
                    county=random.choice(COUNTIES),
                    lat_dd83=lat,
                    long_dd83=lon,
                    comments="Seeded location (fake data).",
                )
            )

            # records -> samples chain
            recrd_set_id = uuid.uuid4()
            oid += 1
            s.add(
                NMW_WellRecords(
                    object_id=oid,
                    recrd_set_id=recrd_set_id,
                    well_data_id=well_data_id,
                    recrd_class="Geothermal",
                    action_date=fake.date_time_between("-40y", "-1y"),
                    well_name=f"GEOTHERMAL-{i + 1:04d}",
                    comments="Seeded record (fake data).",
                )
            )
            s.flush()

            sampl_set_id = uuid.uuid4()
            oid += 1
            s.add(
                NMW_WellSamples(
                    object_id=oid,
                    sampl_set_id=sampl_set_id,
                    recrdset_id=recrd_set_id,
                    smp_set_name=f"GT-SAMPLE-{i + 1:04d}",
                    sampl_class="data",
                    geothermal=1,
                    sample_date=fake.date_time_between("-40y", "-1y"),
                    from_depth=0.0,
                    to_depth=total_depth,
                    smp_dp_unt="ft",
                    notes="Seeded sample set (fake data).",
                )
            )
            s.flush()

            # bottom-hole temperature header + readings
            bht_guid = uuid.uuid4()
            s.add(
                NMW_GtBhtHeaders(
                    bht_guid=bht_guid,
                    sampl_set_id=sampl_set_id,
                    bore_dia=round(random.uniform(6, 12), 2),
                    bore_units="in",
                    drill_fluid="mud",
                    temp_unit="F",
                    notes="Seeded BHT header (fake data).",
                )
            )
            s.flush()
            for _ in range(random.randint(1, 3)):
                oid += 1
                depth = round(random.uniform(500, total_depth), 1)
                s.add(
                    NMW_GtBhtData(
                        object_id=oid,
                        bht_guid=bht_guid,
                        depth=depth,
                        bht=round(70 + depth * 0.015 + random.uniform(-5, 5), 1),
                        temp_unit="F",
                        hrs_snce_cir=round(random.uniform(1, 24), 1),
                        date_measrd=fake.date_time_between("-40y", "-1y"),
                    )
                )

            # temperature-vs-depth profile
            for step in range(1, random.randint(3, 6)):
                oid += 1
                depth = round(total_depth * step / 6, 1)
                s.add(
                    NMW_GtTempDepths(
                        object_id=oid,
                        sampl_set_id=sampl_set_id,
                        depth=depth,
                        temp=round(70 + depth * 0.016 + random.uniform(-3, 3), 1),
                        temp_unit="F",
                        intrvl_grad=round(random.uniform(15, 40), 2),
                    )
                )

            # summary heat flow
            oid += 1
            s.add(
                NMW_GtSumHeatFlow(
                    object_id=oid,
                    recrd_set_id=recrd_set_id,
                    sampl_set_id=sampl_set_id,
                    from_depth=0.0,
                    to_depth=total_depth,
                    depth_unit="ft",
                    therml_grad=round(random.uniform(20, 45), 2),
                    grad_unit="C/k",  # GradUnit is varchar(3)
                    therml_cond=round(random.uniform(1.5, 3.5), 2),
                    tcond_unit="W/m",  # TCondUnit is varchar(3)
                    heat_flow=round(random.uniform(40, 120), 1),
                    ht_flow_unit="HFU",  # HtFlowUnit is varchar(3)
                    quality="B",
                    comments="Seeded heat flow (fake data).",
                )
            )

        try:
            s.commit()
            print(f"Geothermal seed complete: {n} wells + child measurements.")
        except Exception as e:
            s.rollback()
            print(f"Error committing geothermal seed data: {e}")
            raise

    print("Geothermal seeding finished.")


if __name__ == "__main__":
    seed_geothermal(8, skip_if_exists=True)
