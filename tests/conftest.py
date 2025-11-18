import uuid

import pytest

from db import *
from db.engine import session_ctx
from tests import groundwater_level_parameter_id, pH_parameter_id


@pytest.fixture()
def location():
    with session_ctx() as session:
        loc = Location(
            notes="these are some test notes",
            point="POINT(-107.949533 33.809665)",
            elevation=2464.9,
            release_status="draft",
        )
        session.add(loc)
        session.commit()
        session.refresh(loc)
        yield loc
        session.delete(loc)
        session.commit()


@pytest.fixture(scope="function")
def second_location():
    with session_ctx() as session:
        location = Location(
            point="POINT (10.2 10.2)",
            elevation=0,
            release_status="draft",
        )
        session.add(location)
        session.commit()
        yield location
        session.delete(location)
        session.commit()


@pytest.fixture()
def water_well_thing(location):
    with session_ctx() as session:
        water_well = Thing(
            name="Test Well",
            first_visit_date="2023-03-03",
            thing_type="water well",
            release_status="draft",
            well_depth=10,
            hole_depth=10,
            well_construction_notes="Test well construction notes",
            well_casing_diameter=5.0,
            well_casing_depth=10.0,
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
        session.refresh(water_well)
        session.refresh(assoc)
        yield water_well
        session.delete(water_well)
        session.delete(assoc)
        session.commit()


@pytest.fixture()
def pvc_well_casing_material(water_well_thing):
    with session_ctx() as session:
        casing_material = WellCasingMaterial(
            thing_id=water_well_thing.id,
            material="PVC",
            release_status="draft",
        )
        session.add(casing_material)
        session.commit()
        yield casing_material
        session.delete(casing_material)
        session.commit()


@pytest.fixture(scope="function")
def steel_well_casing_material(water_well_thing):
    with session_ctx() as session:
        casing_material = WellCasingMaterial(
            thing_id=water_well_thing.id,
            material="Steel",
            release_status="draft",
        )
        session.add(casing_material)
        session.commit()
        yield casing_material
        session.delete(casing_material)
        session.commit()


@pytest.fixture()
def irrigation_well_purpose(water_well_thing):
    with session_ctx() as session:
        purpose = WellPurpose(
            thing_id=water_well_thing.id,
            purpose="Irrigation",
            release_status="draft",
        )
        session.add(purpose)
        session.commit()
        yield purpose
        session.delete(purpose)
        session.commit()


@pytest.fixture()
def domestic_well_purpose(water_well_thing):
    with session_ctx() as session:
        purpose = WellPurpose(
            thing_id=water_well_thing.id,
            purpose="Domestic",
            release_status="draft",
        )
        session.add(purpose)
        session.commit()
        yield purpose
        session.delete(purpose)
        session.commit()


@pytest.fixture()
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
        session.delete(screen)
        session.commit()


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


@pytest.fixture()
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
        session.delete(id_link)
        session.commit()


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


@pytest.fixture()
def spring_thing(location):
    with session_ctx() as session:
        spring = Thing(
            name="Test Spring",
            first_visit_date="2023-03-03",
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
        session.delete(assoc)
        session.commit()


@pytest.fixture(scope="function")
def second_spring_thing(location):
    with session_ctx() as session:
        spring = Thing(
            name="Second Test Spring",
            first_visit_date="2023-03-03",
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
        session.delete(assoc)
        session.commit()


@pytest.fixture()
def sensor():
    with session_ctx() as session:
        sensor = Sensor(
            name=f"Test Sensor {uuid.uuid4()}",
            sensor_type="Pressure Transducer",
            model="Model X",
            serial_no="123456",
            pcn_number="PCN123456",
            owner_agency="NMBGMR",
            sensor_status="In Service",
            notes="Test equipment",
            release_status="draft",
        )
        session.add(sensor)
        session.commit()
        yield sensor
        session.delete(sensor)
        session.commit()


@pytest.fixture(scope="function")
def second_sensor():
    with session_ctx() as session:
        sensor = Sensor(
            name="Test Sensor 2",
            sensor_type="Pressure Transducer",
            model="Model X",
            serial_no="123456",
            pcn_number="PCN123456",
            owner_agency="NMBGMR",
            sensor_status="In Service",
            notes="Test equipment",
            release_status="draft",
        )
        session.add(sensor)
        session.commit()
        yield sensor
        session.delete(sensor)
        session.commit()


@pytest.fixture()
def sensor_to_water_well_thing_deployment(sensor, water_well_thing):
    with session_ctx() as session:
        deployment = Deployment(
            sensor_id=sensor.id,
            thing_id=water_well_thing.id,
            installation_date="2023-01-01",
            removal_date=None,
            recording_interval=24,
            recording_interval_units="hour",
            hanging_cable_length=10,
            hanging_point_height=0,
            hanging_point_description="hang 10",
            notes="deployment fixture",
        )
        session.add(deployment)
        session.commit()
        yield deployment
        session.delete(deployment)
        session.commit()


@pytest.fixture()
def contact(water_well_thing):
    with session_ctx() as session:
        contact = Contact(
            release_status="private",
            name="Test Contact",
            role="Owner",
            contact_type="Primary",
            organization="NMBGMR",
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
        session.delete(contact)
        session.delete(association)
        session.commit()


@pytest.fixture()
def incomplete_nma_phone_1(contact):
    with session_ctx() as session:
        nma_phone = IncompleteNMAPhone(
            phone_number="9999999",
            contact_id=contact.id,
        )
        session.add(nma_phone)
        session.commit()
        session.refresh(nma_phone)
        yield nma_phone
        session.delete(nma_phone)
        session.commit()


@pytest.fixture()
def incomplete_nma_phone_2(contact):
    with session_ctx() as session:
        nma_phone = IncompleteNMAPhone(
            phone_number="8888888",
            contact_id=contact.id,
        )
        session.add(nma_phone)
        session.commit()
        session.refresh(nma_phone)
        yield nma_phone
        session.delete(nma_phone)
        session.commit()


@pytest.fixture()
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
        session.delete(address)
        session.commit()


@pytest.fixture()
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
        session.delete(email)
        session.commit()


@pytest.fixture()
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
        session.delete(phone)
        session.commit()


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
            organization="NMBGMR",
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        yield contact

        session.delete(contact)
        session.commit()


@pytest.fixture()
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
        session.delete(asset)
        session.commit()


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


@pytest.fixture()
def field_event(water_well_thing):
    with session_ctx() as session:
        field_event = FieldEvent(
            thing_id=water_well_thing.id,
            event_date="2025-01-01T00:00:00Z",
            notes="field event fixture notes",
            release_status="draft",
        )
        session.add(field_event)
        session.commit()
        yield field_event
        session.delete(field_event)
        session.commit()


@pytest.fixture()
def field_event_participant(field_event, contact):
    with session_ctx() as session:
        field_event_participant = FieldEventParticipant(
            field_event_id=field_event.id,
            contact_id=contact.id,
            participant_role="Lead",
        )
        session.add(field_event_participant)
        session.commit()
        yield field_event_participant
        session.delete(field_event_participant)
        session.commit()


@pytest.fixture()
def groundwater_level_field_activity(field_event):
    with session_ctx() as session:
        field_activity = FieldActivity(
            field_event_id=field_event.id,
            activity_type="groundwater level",
            notes="field activity fixture notes",
            release_status="draft",
        )
        session.add(field_activity)
        session.commit()
        yield field_activity
        session.delete(field_activity)
        session.commit()


@pytest.fixture()
def water_chemistry_field_activity(field_event):
    with session_ctx() as session:
        field_activity = FieldActivity(
            field_event_id=field_event.id,
            activity_type="water chemistry",
            notes="field activity fixture notes",
            release_status="draft",
        )
        session.add(field_activity)
        session.commit()
        yield field_activity
        session.delete(field_activity)
        session.commit()


@pytest.fixture()
def groundwater_level_sample(groundwater_level_field_activity, field_event_participant):
    with session_ctx() as session:
        sample = Sample(
            field_activity_id=groundwater_level_field_activity.id,
            field_event_participant_id=field_event_participant.id,
            sample_date="2025-01-01T12:00:00Z",
            sample_name="groundwater level sample name",
            sample_matrix="water",
            sample_method="Steel-tape measurement",
            qc_type="Normal",
            depth_top=None,
            depth_bottom=None,
            notes="groundwater level sample fixture notes",
            release_status="draft",
        )
        session.add(sample)
        session.commit()
        yield sample
        session.delete(sample)
        session.commit()


@pytest.fixture()
def water_chemistry_sample(water_chemistry_field_activity, field_event_participant):
    with session_ctx() as session:
        sample = Sample(
            field_activity_id=water_chemistry_field_activity.id,
            field_event_participant_id=field_event_participant.id,
            sample_date="2025-01-01T13:00:00Z",
            sample_name="water chemistry sample name",
            sample_matrix="water",
            sample_method="grab sample",
            qc_type="Normal",
            depth_top=None,
            depth_bottom=None,
            notes="water chemistry sample fixture notes",
            release_status="draft",
        )
        session.add(sample)
        session.commit()
        yield sample
        session.delete(sample)
        session.commit()


@pytest.fixture(scope="function")
def sample_to_delete(water_chemistry_field_activity, field_event_participant):
    with session_ctx() as session:
        sample = Sample(
            field_activity_id=water_chemistry_field_activity.id,
            field_event_participant_id=field_event_participant.id,
            sample_date="2025-01-01T13:00:00Z",
            sample_name="sample to delete",
            sample_matrix="water",
            sample_method="grab sample",
            qc_type="Normal",
            depth_top=None,
            depth_bottom=None,
            notes="water chemistry sample fixture notes",
            release_status="draft",
        )
        session.add(sample)
        session.commit()
        yield sample
        session.delete(sample)
        session.commit()


@pytest.fixture()
def groundwater_level_observation(sensor, groundwater_level_sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:04:00Z",
            sample_id=groundwater_level_sample.id,
            sensor_id=sensor.id,
            parameter_id=groundwater_level_parameter_id,
            release_status="draft",
            value=10.0,
            unit="ft",
            measuring_point_height=5.0,
            groundwater_level_reason="Water level not affected",
        )
        session.add(observation)
        session.commit()
        yield observation
        session.delete(observation)
        session.commit()


@pytest.fixture()
def water_chemistry_observation(sensor, water_chemistry_sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:03:00Z",
            sample_id=water_chemistry_sample.id,
            sensor_id=sensor.id,
            parameter_id=pH_parameter_id,
            release_status="draft",
            value=4.0,
            unit="dimensionless",
        )
        session.add(observation)
        session.commit()
        yield observation
        session.delete(observation)
        session.commit()


@pytest.fixture()
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
        session.delete(observation)
        session.commit()


@pytest.fixture(scope="function")
def observation_to_delete(water_chemistry_sample, sensor):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2019-01-01T00:03:00Z",
            sample_id=water_chemistry_sample.id,
            sensor_id=sensor.id,
            parameter_id=pH_parameter_id,
            release_status="draft",
            value=4.0,
            unit="dimensionless",
        )
        session.add(observation)
        session.commit()
        yield observation
        session.delete(observation)
        session.commit()


# @pytest.fixture()
# def parameter_water_chemistry():
#     """
#     Fixture to create a Parameter for testing.
#     """
#     with session_ctx() as session:
#         parameter = Parameter(
#             parameter_name="pH",
#             parameter_type="Field Parameter",
#             matrix="groundwater",
#             cas_number="7440-38-2",
#             default_unit="dimensionless",
#             release_status="draft",
#         )
#         session.add(parameter)
#         session.commit()
#         yield parameter
#         session.delete(parameter)
#         session.commit()


# @pytest.fixture()
# def parameter_groundwater():
#     """
#     Fixture to create a Parameter for testing.
#     """
#     with session_ctx() as session:
#         parameter = Parameter(
#             parameter_name="groundwater level",
#             parameter_type="Field Parameter",
#             matrix="groundwater",
#             cas_number=None,
#             default_unit="ft",
#             release_status="draft",
#         )
#         session.add(parameter)
#         session.commit()
#         yield parameter
#         session.delete(parameter)
#         session.commit()


@pytest.fixture()
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
        session.delete(group)
        session.delete(group_thing_association)
        session.commit()


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

        session.delete(group)
        session.delete(group_thing_association)
        session.commit()


@pytest.fixture()
def lexicon_category():
    with session_ctx() as session:
        category = LexiconCategory(
            name="first test category", description="describes the first test category"
        )
        session.add(category)
        session.commit()
        session.refresh(category)
        yield category
        session.delete(category)
        session.commit()


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


@pytest.fixture()
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
        session.delete(term)
        session.delete(term_category_association)
        session.commit()


@pytest.fixture()
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

        session.delete(term)
        session.delete(term_category_association)
        session.commit()


@pytest.fixture()
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

        session.delete(term)
        session.delete(term_category_association)
        session.commit()


@pytest.fixture()
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

        session.delete(term)
        session.delete(term_category_association)
        session.commit()


@pytest.fixture()
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
        session.delete(triple)
        session.commit()


@pytest.fixture()
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
        session.delete(triple)
        session.commit()
