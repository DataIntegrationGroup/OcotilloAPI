"""
Populates the database with interconnected fake data for frontend CI testing.

Run with:
    docker compose exec -T app python -m transfers.seed
"""

import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from geoalchemy2.elements import WKTElement
from sqlalchemy import select

# Core models
from db.analysis_method import AnalysisMethod
from db.contact import Address, Contact, Email, Phone, ThingContactAssociation
from db.deployment import Deployment
from db.engine import session_ctx
from db.field import FieldActivity, FieldEvent, FieldEventParticipant
from db.lexicon import (
    LexiconCategory,
    LexiconTerm,
    LexiconTermCategoryAssociation,
)
from db.location import Location, LocationThingAssociation
from db.measuring_point_history import MeasuringPointHistory
from db.notes import Notes
from db.observation import Observation
from db.parameter import Parameter
from db.sample import Sample
from db.sensor import Sensor
from db.thing import (
    MonitoringFrequencyHistory,
    Thing,
    ThingIdLink,
    WellCasingMaterial,
    WellPurpose,
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


def ensure_seed_prereqs() -> None:
    """Ensure that lexicon and parameter data exist before seeding."""
    from core.initializers import init_lexicon, init_parameter

    with session_ctx() as s:
        has_lexicon = s.scalar(select(LexiconTerm.id).limit(1)) is not None
        has_parameter = s.scalar(select(Parameter.id).limit(1)) is not None

    if not has_lexicon:
        init_lexicon()
    if not has_parameter:
        init_parameter()


def seed_data_exists() -> bool:
    with session_ctx() as s:
        return s.scalar(select(Contact.id).limit(1)) is not None


def seed_all(n: int = 5, skip_if_exists: bool = False):
    """Seed roughly `n` of each main entity and connect them."""
    if skip_if_exists and seed_data_exists():
        return
    ensure_seed_prereqs()
    new_mexico_bounds = [
        (36.9, -106.6),  # Taos area
        (35.1, -106.6),  # Albuquerque
        (32.3, -106.8),  # Las Cruces
        (34.4, -103.2),  # Clovis
        (36.7, -108.2),  # Farmington
    ]

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
        relation_terms = get_terms_by_category(s, "relation")
        analysis_method_type_terms = get_terms_by_category(s, "analysis_method_type")
        sample_method_terms = get_terms_by_category(s, "sample_method")
        activity_type_terms = get_terms_by_category(s, "activity_type")
        sensor_type_terms = get_terms_by_category(s, "sensor_type")
        email_type_terms = get_terms_by_category(s, "email_type")
        phone_type_terms = get_terms_by_category(s, "phone_type")
        address_type_terms = get_terms_by_category(s, "address_type")
        well_purpose_terms = get_terms_by_category(s, "well_purpose")
        casing_material_terms = get_terms_by_category(s, "casing_material")
        monitoring_frequency_terms = get_terms_by_category(s, "monitoring_frequency")
        note_type_terms = get_terms_by_category(s, "note_type")
        participant_role_terms = get_terms_by_category(s, "participant_role")

        # 1. Contacts with emails, phones, and addresses
        for _ in range(n):
            c = Contact(
                name=fake.name(),
                organization=random.choice(organization_terms).term,
                role=random.choice(["Hydrologist", "Technician", "Geologist"]),
                contact_type="Primary",
            )
            s.add(c)
            s.flush()  # Need ID for related records

            # Add email
            email = Email(
                contact_id=c.id,
                email=fake.email(),
                email_type=random.choice(email_type_terms).term,
                release_status="public",
            )
            s.add(email)

            # Add phone
            phone = Phone(
                contact_id=c.id,
                phone_number=fake.numerify("##########")[:20],
                phone_type=random.choice(phone_type_terms).term,
                release_status="public",
            )
            s.add(phone)

            # Add address
            addr = Address(
                contact_id=c.id,
                address_line_1=fake.street_address(),
                address_line_2=(
                    fake.secondary_address() if random.random() > 0.5 else None
                ),
                city=fake.city(),
                state="New Mexico",
                postal_code=fake.zipcode(),
                country="United States",
                address_type=random.choice(address_type_terms).term,
                release_status="public",
            )
            s.add(addr)

            contacts.append(c)

        # 2. Locations
        for _ in range(n):
            # Generate coordinates roughly within New Mexico's bounding box
            base_lat, base_lon = random.choice(new_mexico_bounds)
            lat = round(base_lat + random.uniform(-0.3, 0.3), 6)
            lon = round(base_lon + random.uniform(-0.3, 0.3), 6)

            loc = Location(
                point=WKTElement(f"POINT({lon} {lat})", srid=4326),
                elevation=round(fake.random_number(digits=3), 2),
                release_status="public",
            )
            s.add(loc)
            s.flush()  # Need ID for notes

            # Add a note for the location
            if note_type_terms:
                note = Notes(
                    target_id=loc.id,
                    target_table="Location",
                    note_type=random.choice(note_type_terms).term,
                    content=fake.sentence(),
                    release_status="public",
                )
                s.add(note)

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

        # 4. Things (Water Wells) & related records
        for i in range(n):
            t = Thing(
                name=f"WELL-{i + 1:04d}",
                thing_type="water well",
                first_visit_date=fake.date_between("-2y", "today"),
                well_depth=random.uniform(50, 500),
                hole_depth=random.uniform(50, 500),
                well_driller_name=fake.name(),
                well_casing_diameter=random.uniform(4, 8),
                well_casing_depth=random.uniform(10, 50),
                release_status="public",
            )
            s.add(t)
            s.flush()  # Need ID for related records

            # Add measuring point history (required for measuring_point_height/description)
            mph = MeasuringPointHistory(
                thing_id=t.id,
                measuring_point_height=round(random.uniform(0.5, 3.0), 2),
                measuring_point_description=fake.sentence(),
                start_date=t.first_visit_date or fake.date_between("-2y", "today"),
                end_date=None,
                reason="Initial measuring point record",
                release_status="public",
            )
            s.add(mph)

            # Add monitoring frequency history
            if monitoring_frequency_terms:
                mfh = MonitoringFrequencyHistory(
                    thing_id=t.id,
                    monitoring_frequency=random.choice(monitoring_frequency_terms).term,
                    start_date=t.first_visit_date or fake.date_between("-2y", "today"),
                    end_date=None,
                    release_status="public",
                )
                s.add(mfh)

            # Add well purposes
            if well_purpose_terms:
                num_purposes = random.randint(1, 2)
                selected_purposes = random.sample(
                    well_purpose_terms, k=min(num_purposes, len(well_purpose_terms))
                )
                for purpose_term in selected_purposes:
                    wp = WellPurpose(
                        thing_id=t.id,
                        purpose=purpose_term.term,
                        release_status="public",
                    )
                    s.add(wp)

            # Add well casing materials
            if casing_material_terms:
                num_materials = random.randint(1, 2)
                selected_materials = random.sample(
                    casing_material_terms,
                    k=min(num_materials, len(casing_material_terms)),
                )
                for material_term in selected_materials:
                    wcm = WellCasingMaterial(
                        thing_id=t.id,
                        material=material_term.term,
                        release_status="public",
                    )
                    s.add(wcm)

            # Add notes for the thing
            if note_type_terms:
                note = Notes(
                    target_id=t.id,
                    target_table="Thing",
                    note_type=random.choice(note_type_terms).term,
                    content=fake.sentence(),
                    release_status="public",
                )
                s.add(note)

            things.append(t)

        s.flush()

        # Associate contacts with things
        for t in things:
            assigned_contacts = random.sample(contacts, k=min(2, len(contacts)))
            for c in assigned_contacts:
                assoc = ThingContactAssociation(
                    thing_id=t.id,
                    contact_id=c.id,
                )
                s.add(assoc)

        # Associate locations with things - ensure every thing has at least one location
        # First, assign one location to each thing (required for current_location property)
        for i, t in enumerate(things):
            loc = locations[i % len(locations)]  # Cycle through locations
            assoc = LocationThingAssociation(
                location_id=loc.id,
                thing_id=t.id,
                effective_start=datetime.now(timezone.utc),
                effective_end=None,
            )
            s.add(assoc)

        s.flush()  # Need to flush to get associations loaded

        # Add ThingIdLinks
        for t in things:
            for _ in range(random.randint(1, 3)):
                chosen_org = random.choice(organization_terms)
                link = ThingIdLink(
                    thing_id=t.id,
                    relation=random.choice(relation_terms).term,
                    alternate_id=chosen_org.id,
                    alternate_organization=chosen_org.term,
                    release_status="public",
                )
                s.add(link)

        # 5. FieldEvent, FieldActivity, FieldEventParticipant, Sensors & Deployments
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

        # Add field event participants (contacts who participated)
        field_event_participants: list[FieldEventParticipant] = []
        for fe in field_events:
            # Add 1-2 participants per field event
            num_participants = random.randint(1, 2)
            selected_contacts = random.sample(
                contacts, k=min(num_participants, len(contacts))
            )
            for contact in selected_contacts:
                fep = FieldEventParticipant(
                    field_event_id=fe.id,
                    contact_id=contact.id,
                    participant_role=(
                        random.choice(participant_role_terms).term
                        if participant_role_terms
                        else "Participant"
                    ),
                    release_status="public",
                )
                s.add(fep)
                field_event_participants.append(fep)

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

        # Create sensors
        for i in range(n):
            sn = Sensor(
                name=f"Sensor-{i + 1}",
                sensor_type=random.choice(sensor_type_terms).term,
                serial_no=fake.unique.bothify(text="SN-####"),
                release_status="public",
            )
            sensors.append(sn)
            s.add(sn)

        s.flush()

        # Create deployments
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
                field_event_participant_id=(
                    random.choice(field_event_participants).id
                    if field_event_participants
                    else None
                ),
            )
            t = random.choice(things)
            samp.thing_id = t.id
            samples.append(samp)
            s.add(samp)

        s.flush()

        # Create observations
        for i in range(n * 2):
            obs = Observation(
                sample=random.choice(samples),
                sensor=random.choice(sensors),
                parameter=random.choice(parameters),
                analysis_method=random.choice(methods),
                observation_datetime=fake.date_time_this_month(),
                value=round(random.uniform(0, 500), 2),
                unit="mg/L",
                release_status="public",
            )
            observations.append(obs)
            s.add(obs)

        try:
            s.commit()
            print(
                f"Seed complete: {len(contacts)} contacts, {len(locations)} locations, "
                + f"{len(things)} things, {len(sensors)} sensors, {len(samples)} samples, "
                + f"{len(observations)} observations."
            )
        except Exception as e:
            s.rollback()
            print(f"Error committing seed data: {e}")
            raise


if __name__ == "__main__":
    seed_all(5)
