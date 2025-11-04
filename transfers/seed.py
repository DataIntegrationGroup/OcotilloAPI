"""
Populates the database with interconnected fake data for frontend CI testing.

Run with:
    docker compose exec -T app python -m transfers.seed
"""

import random
from datetime import datetime, timedelta, timezone
from faker import Faker
from db.engine import session_ctx
from sqlalchemy import select
from geoalchemy2.elements import WKTElement

# Core models
from db.contact import Contact, ThingContactAssociation
from db.location import Location, LocationThingAssociation
from db.thing import Thing
from db.sensor import Sensor
from db.deployment import Deployment
from db.field import FieldEvent, FieldActivity
from db.sample import Sample
from db.observation import Observation
from db.parameter import Parameter
from db.analysis_method import AnalysisMethod
from db.regulatory_limit import RegulatoryLimit
from db.transducer import TransducerObservation
from db.status_history import StatusHistory
from db.lexicon import (
    LexiconTerm,
    LexiconCategory,
    LexiconTermCategoryAssociation,
)

fake = Faker()
Faker.seed(42)
random.seed(42)


def get_terms_by_category(s, category_name: str) -> list[LexiconTerm]:
    return list(
        s.scalars(
            select(LexiconTerm)
            .join(LexiconTermCategoryAssociation)
            .join(LexiconCategory)
            .where(LexiconCategory.name == category_name)
        )
    )


def seed_all(n: int = 5):
    """Seed roughly `n` of each main entity and connect them."""
    with session_ctx() as s:
        contacts: list[Contact] = []
        locations: list[Location] = []
        things: list[Thing] = []
        sensors: list[Sensor] = []
        parameters: list[Parameter] = []
        methods: list[AnalysisMethod] = []
        field_events: list[FieldEvent] = []
        field_activities: list[FieldActivity] = []
        samples: list[Sample] = []
        observations: list[Observation] = []

        # 0. Lexicons
        organization_terms = get_terms_by_category(s, "organization")
        analysis_method_type_terms = get_terms_by_category(s, "analysis_method_type")
        sample_method_terms = get_terms_by_category(s, "sample_method")
        activity_type_terms = get_terms_by_category(s, "activity_type")
        sensor_type_terms = get_terms_by_category(s, "sensor_type")

        # 1. Contacts
        for _ in range(n):
            c = Contact(
                name=fake.name(),
                organization=random.choice(organization_terms).term,
                role=random.choice(["Hydrologist", "Technician", "Geologist"]),
                contact_type="Primary",
            )
            s.add(c)
            contacts.append(c)

        # 2. Locations
        for _ in range(n):
            lat = round(fake.latitude(), 6)
            lon = round(fake.longitude(), 6)

            loc = Location(
                point=WKTElement(f"POINT({lon} {lat})", srid=4326),
                elevation=round(fake.random_number(digits=3), 2),
                county=fake.city(),
                notes=fake.sentence(),
                elevation_accuracy=random.uniform(0.1, 5.0),
                coordinate_accuracy=random.uniform(0.1, 10.0),
                release_status="public",
            )
            s.add(loc)
            locations.append(loc)

        # 3. Retrieve existing Parameters & Methods
        #
        # If the environment variable MODE=development is set
        # then it will initialize both the parameter and lexicon tables.
        # See core/app.py for details
        parameters = list(s.scalars(select(Parameter)).all())
        if not parameters:
            raise RuntimeError("No parameters found — ensure init_parameter() ran.")

        method_codes = ["ASTM-D1293", "EPA-150.1", "SM-4500-O"]
        for m in method_codes:
            am = AnalysisMethod(
                analysis_method_code=m,
                analysis_method_name=f"Method {m}",
                analysis_method_type=random.choice(analysis_method_type_terms).term,
                source_organization=random.choice(organization_terms).term,
            )
            s.add(am)
            methods.append(am)

        s.flush()

        # 4. Things (Water Wells) & ThingContactAssociation & LocationThingAssociation
        for i in range(n):
            t = Thing(
                name=f"WELL-{i + 1:04d}",
                thing_type="water well",
                first_visit_date=fake.date_between("-2y", "today"),
                well_depth=random.uniform(50, 500),
                hole_depth=random.uniform(50, 500),
                well_construction_notes=fake.sentence(),
                well_casing_diameter=random.uniform(4, 8),
                well_casing_depth=random.uniform(10, 50),
                release_status="public",
            )
            s.add(t)
            things.append(t)

        s.flush()

        for t in things:
            assigned_contacts = random.sample(contacts, k=min(2, len(contacts)))
            for c in assigned_contacts:
                assoc = ThingContactAssociation(
                    thing_id=t.id,
                    contact_id=c.id,
                )
                s.add(assoc)

        for loc in locations:
            assigned_things = random.sample(things, k=min(2, len(things)))
            for t in assigned_things:
                assoc = LocationThingAssociation(
                    location_id=loc.id,
                    thing_id=t.id,
                    effective_start=datetime.now(timezone.utc),
                    effective_end=None,
                )
                s.add(assoc)

        # 5. FieldEvent, FieldActivity, Sensors & Deployments
        for t in things:
            fe = FieldEvent(
                thing_id=t.id,
                event_date=datetime.now(timezone.utc),
                notes=f"Auto-generated field event for {t.name}",
                release_status="public",
            )
            s.add(fe)
            field_events.append(fe)

        s.flush()

        for fe in field_events:
            fa = FieldActivity(
                field_event_id=fe.id,
                activity_type=random.choice(activity_type_terms).term,
                notes=f"Auto-generated activity for event {fe.id}",
                release_status="public",
            )
            s.add(fa)
            field_activities.append(fa)

        s.flush()

        for i in range(n):
            sn = Sensor(
                name=f"Sensor-{i + 1}",
                sensor_type=random.choice(sensor_type_terms).term,
                serial_no=fake.unique.bothify(text="SN-####"),
            )
            sensors.append(sn)
            s.add(sn)

        s.flush()
        deployments: list[Deployment] = []
        for t in things:
            sn = random.choice(sensors)
            d = Deployment(
                thing=t,
                sensor=sn,
                installation_date=datetime.now(timezone.utc)
                - timedelta(days=random.randint(30, 180)),
                removal_date=None,
            )
            deployments.append(d)
            s.add(d)

        # 6. Samples & Observations
        for i in range(n):
            samp = Sample(
                field_activity_id=random.choice(field_activities).id,
                sample_name=f"SMPL-{fake.random_int(1000, 9999)}",
                sample_matrix="water",
                sample_method=random.choice(sample_method_terms).term,
                sample_date=fake.date_time_this_year(),
            )
            t = random.choice(things)
            samp.thing_id = t.id
            samples.append(samp)
            s.add(samp)

        s.flush()
        for i in range(n * 2):
            obs = Observation(
                sample=random.choice(samples),
                sensor=random.choice(sensors),
                parameter=random.choice(parameters),
                analysis_method=random.choice(methods),
                observation_datetime=fake.date_time_this_month(),
                value=round(random.uniform(0, 500), 2),
                unit="mg/L",
            )
            observations.append(obs)
            s.add(obs)

        # 7. Regulatory Limits
        for prm in parameters:
            rl = RegulatoryLimit(
                parameter=prm,
                limit_value=random.uniform(50, 1000),
                limit_unit="mg/L",
            )
            s.add(rl)

        # 8. Status History (for Things)
        for t in things:
            st = StatusHistory(
                status_type="Use Status",
                status_value=random.choice(["Active", "Inactive", "Decommissioned"]),
                start_date=datetime.now(timezone.utc)
                - timedelta(days=random.randint(100, 500)),
                statusable_id=t.id,
                statusable_type="Thing",
                reason="Initial test seed status",
            )
            s.add(st)

        # 9. Transducer Observations
        for d in deployments:
            for _ in range(3):
                tobs = TransducerObservation(
                    parameter=random.choice(parameters),
                    deployment_id=d.id,
                    observation_datetime=datetime.now(timezone.utc)
                    - timedelta(hours=random.randint(1, 500)),
                    value=round(random.uniform(10, 100), 2),
                )
                s.add(tobs)

        s.commit()

        print(
            f"Seed complete: {len(contacts)} contacts, {len(locations)} locations, "
            + f"{len(things)} things, {len(sensors)} sensors, {len(samples)} samples, "
            + f"{len(observations)} observations."
        )


if __name__ == "__main__":
    seed_all(5)
