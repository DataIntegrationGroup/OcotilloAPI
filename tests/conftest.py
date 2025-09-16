import pytest
import uuid

from db import *
from db.engine import session_ctx


@pytest.fixture(scope="session")
def location():
    with session_ctx() as session:
        loc = Location(
            # name="first location",
            notes="these are some test notes",
            point="POINT(-107.949533 33.809665)",
            elevation=2464.9,
            release_status="draft",
            elevation_accuracy=100,
            elevation_method="Survey-grade GPS",
            coordinate_accuracy=50,
            coordinate_method="GPS, uncorrected",
            state="New Mexico",
            county="Catron",
            quad_name="Luera Mountains West",
        )
        session.add(loc)
        session.commit()
        session.refresh(loc)
        yield loc

        session.close()


@pytest.fixture(scope="function")
def second_location():
    with session_ctx() as session:
        location = Location(
            # name="second location",
            point="POINT (10.2 10.2)",
            elevation=0,
            release_status="draft",
        )
        session.add(location)
        session.commit()
        yield location
        session.delete(location)
        session.commit()


@pytest.fixture(scope="session")
def water_well_thing(location):
    with session_ctx() as session:
        water_well = Thing(
            name="Test Well",
            thing_type="water well",
            release_status="draft",
            well_type="Production",
            well_depth=10,
            hole_depth=10,
            well_construction_notes="Test well construction notes",
        )
        session.add(water_well)
        session.commit()
        session.refresh(water_well)

        assoc = LocationThingAssociation()
        assoc.location_id = location.id
        assoc.thing_id = water_well.id
        assoc.effective_start = "2025-02-01T00:00:00Z"
        session.add(assoc)
        session.commit()
        yield water_well


@pytest.fixture(scope="session")
def well_screen(water_well_thing):
    with session_ctx() as session:
        screen = WellScreen(
            thing_id=water_well_thing.id,
            screen_depth_top=10.0,
            screen_depth_bottom=20.0,
            screen_type="PVC",
            screen_description="Test well screen description",
            release_status="draft",
        )
        session.add(screen)
        session.commit()
        yield screen


@pytest.fixture(scope="function")
def second_well_screen(water_well_thing):
    with session_ctx() as session:
        screen = WellScreen(
            thing_id=water_well_thing.id,
            screen_depth_top=30.0,
            screen_depth_bottom=40.0,
            screen_type="PVC",
            screen_description="Test well screen description",
            release_status="private",
        )
        session.add(screen)
        session.commit()
        yield screen
        session.delete(screen)
        session.commit()


@pytest.fixture(scope="session")
def thing_id_link(water_well_thing):
    with session_ctx() as session:
        id_link = ThingIdLink(
            thing_id=water_well_thing.id,
            relation="same_as",
            alternate_id="4321-1234",
            alternate_organization="USGS",
            release_status="private",
        )
        session.add(id_link)
        session.commit()
        yield id_link


@pytest.fixture(scope="function")
def second_thing_id_link(water_well_thing):
    with session_ctx() as session:
        id_link = ThingIdLink(
            thing_id=water_well_thing.id,
            relation="same_as",
            alternate_id="4321-1234",
            alternate_organization="USGS",
            release_status="private",
        )
        session.add(id_link)
        session.commit()
        yield id_link
        session.delete(id_link)
        session.commit()


@pytest.fixture(scope="session")
def spring_thing(location):
    with session_ctx() as session:
        spring = Thing(
            name="Test Spring",
            thing_type="spring",
            release_status="draft",
            spring_type="Artesian",
        )
        session.add(spring)
        session.commit()
        session.refresh(spring)

        assoc = LocationThingAssociation()
        assoc.location_id = location.id
        assoc.thing_id = spring.id
        session.add(assoc)
        session.commit()
        yield spring


@pytest.fixture(scope="function")
def second_spring_thing(location):
    with session_ctx() as session:
        spring = Thing(
            name="Second Test Spring",
            thing_type="spring",
            release_status="draft",
            spring_type="Artesian",
        )
        session.add(spring)
        session.commit()
        session.refresh(spring)

        assoc = LocationThingAssociation()
        assoc.location_id = location.id
        assoc.thing_id = spring.id
        session.add(assoc)
        session.commit()
        yield spring
        session.delete(spring)
        session.commit()


@pytest.fixture(scope="session")
def sensor():
    with session_ctx() as session:
        sensor = Sensor(
            name=f"Test Sensor {uuid.uuid4()}",
            model="Model X",
            serial_no="123456",
            datetime_installed="2023-01-01T00:00:00Z",
            datetime_removed="2023-01-02T00:00:00Z",
            recording_interval=60,
            notes="Test equipment",
            release_status="draft",
        )
        session.add(sensor)
        session.commit()
        yield sensor


@pytest.fixture(scope="function")
def second_sensor():
    with session_ctx() as session:
        sensor = Sensor(
            name="Test Sensor 2",
            model="Model X",
            serial_no="123456",
            datetime_installed="2023-01-01T00:00:00Z",
            datetime_removed="2023-01-02T00:00:00Z",
            recording_interval=60,
            notes="Test equipment",
            release_status="draft",
        )
        session.add(sensor)
        session.commit()
        yield sensor
        session.delete(sensor)
        session.commit()


@pytest.fixture(scope="session")
def contact(water_well_thing):
    with session_ctx() as session:
        contact = Contact(
            release_status="private",
            name="Test Contact",
            role="Owner",
            contact_type="Primary",
            organization="Test Organization",
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        association = ThingContactAssociation(
            thing_id=water_well_thing.id, contact_id=contact.id
        )
        session.add(association)
        session.commit()
        session.refresh(association)

        yield contact


@pytest.fixture(scope="session")
def address(contact):
    with session_ctx() as session:
        address = Address(
            release_status="private",
            address_line_1="123 Main St",
            address_line_2="Apt 4B",
            city="Test City",
            state="NM",
            postal_code="87501",
            country="United States",
            address_type="Primary",
            contact_id=contact.id,
        )
        session.add(address)
        session.commit()
        session.refresh(address)
        yield address


@pytest.fixture(scope="session")
def email(contact):
    with session_ctx() as session:
        email = Email(
            email="test@example.com",
            email_type="Primary",
            contact_id=contact.id,
            release_status="private",
        )
        session.add(email)
        session.commit()
        session.refresh(email)
        yield email


@pytest.fixture(scope="session")
def phone(contact):
    with session_ctx() as session:
        phone = Phone(
            phone_number="+15051234567",
            phone_type="Mobile",
            contact_id=contact.id,
            release_status="private",
        )
        session.add(phone)
        session.commit()
        session.refresh(phone)
        yield phone


@pytest.fixture(scope="function")
def second_contact():
    with session_ctx() as session:
        contact = Contact(
            release_status="private",
            name="Test Second Contact",
            role="Owner",
            contact_type="Primary",
            organization=None,
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        yield contact

        session.delete(contact)
        session.commit()


@pytest.fixture(scope="function")
def second_email(second_contact):
    with session_ctx() as session:
        email = Email(
            email="testsecondcontact@gmail.com",
            email_type="Primary",
            contact_id=second_contact.id,
            release_status="private",
        )
        session.add(email)
        session.commit()
        session.refresh(email)
        yield email
        session.delete(email)
        session.commit()


@pytest.fixture(scope="function")
def second_phone(second_contact):
    with session_ctx() as session:
        phone = Phone(
            phone_number="123-456-7890",
            phone_type="Primary",
            contact_id=second_contact.id,
            release_status="private",
        )
        session.add(phone)
        session.commit()
        session.refresh(phone)
        yield phone
        session.delete(phone)
        session.commit()


@pytest.fixture(scope="function")
def second_address(second_contact):
    with session_ctx() as session:
        address = Address(
            release_status="private",
            address_line_1="456 Secondary St",
            address_line_2="Apt 12A",
            city="Test Metropolis",
            state="NM",
            postal_code="87501",
            country="United States",
            address_type="Primary",
            contact_id=second_contact.id,
        )
        session.add(address)
        session.commit()
        session.refresh(address)
        yield address
        session.delete(address)
        session.commit()


@pytest.fixture(scope="function")
def third_contact():
    with session_ctx() as session:
        contact = Contact(
            release_status="private",
            name=None,
            role="Owner",
            contact_type="Primary",
            organization="Third Organization",
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        yield contact

        session.delete(contact)
        session.commit()


@pytest.fixture(scope="session")
def asset():
    with session_ctx() as session:
        asset = Asset(
            release_status="draft",
            name="Test Asset",
            label="test label",
            mime_type="image/png",
            size=12345,
            storage_service="mock_service",
            storage_path="mock/path/to/asset",
            uri="https://storage.googleapis.com/mock-bucket/mock-asset",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        yield asset


@pytest.fixture(scope="function")
def asset_with_associated_thing(water_well_thing):
    with session_ctx() as session:
        asset = Asset(
            release_status="draft",
            name="Test Asset with water_well_thing",
            label="test label",
            mime_type="application/pdf",
            size=12345,
            storage_service="mock_service",
            storage_path="mock/path/to/asset",
            uri="https://storage.googleapis.com/mock-bucket/mock-asset",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)

        association = AssetThingAssociation(
            asset_id=asset.id, thing_id=water_well_thing.id
        )
        session.add(association)
        session.commit()
        session.refresh(association)

        yield asset
        session.delete(asset)
        session.delete(association)
        session.commit()


@pytest.fixture(scope="function")
def second_asset():
    with session_ctx() as session:
        asset = Asset(
            name="Second test asset",
            label="Second test label",
            mime_type="application/pdf",
            size=2468,
            storage_service="mock_service",
            storage_path="mock/path/to/asset",
            uri="https://storage.googleapis.com/mock-bucket/second-mock-asset",
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        yield asset
        session.delete(asset)
        session.commit()


@pytest.fixture(scope="session")
def groundwater_level_sample(water_well_thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            sample_date="2025-01-01T00:00:00Z",
            thing_id=water_well_thing.id,
            sample_type="groundwater level",
            sampler_name="Test Sampler",
            release_status="draft",
            field_sample_id=f"FS-{uuid.uuid4()}",
            qc_sample="Original",
            sensor_id=sensor.id,
            sample_matrix="groundwater",
            sample_method="manual",
            duplicate_sample_number=0,
            sample_top=None,
            sample_bottom=None,
        )
        session.add(sample)
        session.commit()
        yield sample


@pytest.fixture(scope="session")
def water_chemistry_sample(water_well_thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            sample_date="2025-01-01T00:00:00Z",
            thing_id=water_well_thing.id,
            sample_type="water chemistry",
            sampler_name="Test Sampler",
            release_status="draft",
            field_sample_id=f"FS-{uuid.uuid4()}",
            qc_sample="Original",
            sensor_id=sensor.id,
            sample_matrix="groundwater",
            sample_method="manual",
            duplicate_sample_number=0,
            sample_top=None,
            sample_bottom=None,
        )
        session.add(sample)
        session.commit()
        yield sample


@pytest.fixture(scope="session")
def geothermal_sample(water_well_thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            sample_date="2025-01-01T00:00:00Z",
            thing_id=water_well_thing.id,
            sample_type="geothermal",
            sampler_name="Test Sampler",
            release_status="draft",
            field_sample_id=f"FS-{uuid.uuid4()}",
            qc_sample="Original",
            sensor_id=sensor.id,
            sample_matrix="groundwater",
            sample_method="manual",
            duplicate_sample_number=0,
            sample_top=None,
            sample_bottom=None,
        )
        session.add(sample)
        session.commit()
        yield sample


@pytest.fixture(scope="function")
def second_sample(water_well_thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            thing_id=water_well_thing.id,
            sample_type="groundwater level",
            field_sample_id="FS-9999999",
            sample_date="2025-01-01T00:00:00Z",
            release_status="draft",
            sampler_name="Test Sampler",
            qc_sample="Duplicate",
            sensor_id=sensor.id,
            sample_matrix="groundwater",
            sample_method="manual",
            duplicate_sample_number=3,
            sample_top=2,
            sample_bottom=3,
        )
        session.add(sample)
        session.commit()
        yield sample
        session.delete(sample)
        session.commit()


@pytest.fixture(scope="session")
def groundwater_level_observation(sensor, groundwater_level_sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:04:00Z",
            sample_id=groundwater_level_sample.id,
            sensor_id=sensor.id,
            observed_property="groundwater level",
            release_status="draft",
            value=10.0,
            unit="ft",
            measuring_point_height=5.0,
            level_status="Water level not affected by status",
        )
        session.add(observation)
        session.commit()
        yield observation


@pytest.fixture(scope="session")
def water_chemistry_observation(sensor, water_chemistry_sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:03:00Z",
            sample_id=water_chemistry_sample.id,
            sensor_id=sensor.id,
            observed_property="pH",
            release_status="draft",
            value=4.0,
            unit="dimensionless",
        )
        session.add(observation)
        session.commit()
        yield observation


@pytest.fixture(scope="session")
def geothermal_observation(sensor, geothermal_sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:02:00Z",
            sample_id=geothermal_sample.id,
            sensor_id=sensor.id,
            observed_property="temperature",
            release_status="draft",
            value=20.0,
            unit="deg C",
            observation_depth=200.0,
        )
        session.add(observation)
        session.commit()
        yield observation


@pytest.fixture(scope="function")
def observation_to_delete(water_chemistry_sample, sensor):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2019-01-01T00:03:00Z",
            sample_id=water_chemistry_sample.id,
            sensor_id=sensor.id,
            observed_property="pH",
            release_status="draft",
            value=4.0,
            unit="dimensionless",
        )
        session.add(observation)
        session.commit()
        yield observation


@pytest.fixture(scope="session")
def group(water_well_thing):
    with session_ctx() as session:
        group = Group(
            release_status="draft",
            name="Test Group",
            description="This is a test group.",
            project_area="MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, -106.6 34.2, -107.2 34.2, -107.2 33.6)))",
        )

        session.add(group)
        session.commit()
        session.refresh(group)

        group_thing_association = GroupThingAssociation(
            group_id=group.id, thing_id=water_well_thing.id
        )
        session.add(group_thing_association)
        session.commit()
        session.refresh(group_thing_association)

        yield group


@pytest.fixture(scope="function")
def second_group(water_well_thing):
    with session_ctx() as session:
        group = Group(
            release_status="draft",
            name="Second Test Group",
            description="This is a second test group.",
            project_area="MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, -106.6 34.2, 0 0, -107.2 34.2, -107.2 33.6)))",
        )

        session.add(group)
        session.commit()
        session.refresh(group)

        group_thing_association = GroupThingAssociation(
            group_id=group.id, thing_id=water_well_thing.id
        )
        session.add(group_thing_association)
        session.commit()
        session.refresh(group_thing_association)

        yield group


@pytest.fixture(scope="session")
def lexicon_category():
    with session_ctx() as session:
        category = LexiconCategory(
            name="first test category", description="describes the first test category"
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        yield category


@pytest.fixture(scope="function")
def second_lexicon_category():
    with session_ctx() as session:
        category = LexiconCategory(
            name="second test category",
            description="describes the second test category",
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        yield category
        session.delete(category)
        session.commit()


@pytest.fixture(scope="session")
def lexicon_term(lexicon_category):
    with session_ctx() as session:
        term = LexiconTerm(
            term="first test term",
            definition="defines the first test term",
        )
        session.add(term)
        session.commit()
        session.refresh(term)

        term_category_association = LexiconTermCategoryAssociation(
            term_id=term.id, category_id=lexicon_category.id
        )
        session.add(term_category_association)
        session.commit()
        session.refresh(term_category_association)

        yield term


@pytest.fixture(scope="session")
def second_lexicon_term(lexicon_category):
    with session_ctx() as session:
        term = LexiconTerm(
            term="second test term",
            definition="defines the second test term",
        )
        session.add(term)
        session.commit()
        session.refresh(term)

        term_category_association = LexiconTermCategoryAssociation(
            term_id=term.id, category_id=lexicon_category.id
        )
        session.add(term_category_association)
        session.commit()
        session.refresh(term_category_association)

        yield term


@pytest.fixture(scope="session")
def third_lexicon_term(lexicon_category):
    with session_ctx() as session:
        term = LexiconTerm(
            term="third test term",
            definition="defines the third test term",
        )
        session.add(term)
        session.commit()
        session.refresh(term)

        term_category_association = LexiconTermCategoryAssociation(
            term_id=term.id, category_id=lexicon_category.id
        )
        session.add(term_category_association)
        session.commit()
        session.refresh(term_category_association)

        yield term


@pytest.fixture(scope="session")
def fourth_lexicon_term(lexicon_category):
    with session_ctx() as session:
        term = LexiconTerm(
            term="fourth test term",
            definition="defines the fourth test term",
        )
        session.add(term)
        session.commit()
        session.refresh(term)

        term_category_association = LexiconTermCategoryAssociation(
            term_id=term.id, category_id=lexicon_category.id
        )
        session.add(term_category_association)
        session.commit()
        session.refresh(term_category_association)

        yield term


@pytest.fixture(scope="session")
def lexicon_triple(lexicon_term, second_lexicon_term):
    with session_ctx() as session:
        triple = LexiconTriple(
            subject=lexicon_term.term,
            predicate="related_to",
            object_=second_lexicon_term.term,
        )
        session.add(triple)
        session.commit()
        session.refresh(triple)
        yield triple


@pytest.fixture(scope="session")
def second_lexicon_triple(third_lexicon_term, fourth_lexicon_term):
    with session_ctx() as session:
        triple = LexiconTriple(
            subject=third_lexicon_term.term,
            predicate="related_to",
            object_=fourth_lexicon_term.term,
        )
        session.add(triple)
        session.commit()
        session.refresh(triple)
        yield triple
