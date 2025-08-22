import pytest
import uuid

from db import *
from db.engine import session_ctx
from services.thing_helper import add_thing


@pytest.fixture(scope="session")
def location():
    with session_ctx() as session:
        loc = Location(point="SRID=4326;POINT(0 0)")
        session.add(loc)
        session.commit()
        session.refresh(loc)
        yield loc

        session.close()


@pytest.fixture(scope="session")
def thing(location):
    with session_ctx() as session:
        wt = add_thing(
            session,
            {
                "location_id": location.id,
                "name": "Test Well",
            },
            "water well",
        )

        yield wt

        session.close()


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
        )
        session.add(sensor)
        session.commit()
        yield sensor
        session.close()


@pytest.fixture(scope="session")
def sample(thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            sample_date="2025-01-01T00:00:00Z",
            thing_id=thing.id,
            sample_type="groundwater",
            sampler_name="Test Sampler",
            release_status="draft",
            field_sample_id=f"FS-{uuid.uuid4()}",
            qc_sample="Original",
            sensor_id=sensor.id,
            sample_matrix="water",
            sample_method="manual",
            duplicate_sample_number=0,
            sample_top=None,
            sample_bottom=None,
        )
        session.add(sample)
        session.commit()
        yield sample

        session.close()


@pytest.fixture(scope="session")
def contact(thing):
    with session_ctx() as session:
        contact = Contact(
            name="Test Contact",
            role="Owner",
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        association = ThingContactAssociation(thing_id=thing.id, contact_id=contact.id)
        session.add(association)
        session.commit()
        session.refresh(association)

        yield contact

        session.close()


@pytest.fixture(scope="session")
def address(contact):
    with session_ctx() as session:
        address = Address(
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

        session.close()


@pytest.fixture(scope="session")
def email(contact):
    with session_ctx() as session:
        email = Email(
            email="test@example.com", email_type="Primary", contact_id=contact.id
        )
        session.add(email)
        session.commit()
        session.refresh(email)
        yield email

        session.close()


@pytest.fixture(scope="session")
def phone(contact):
    with session_ctx() as session:
        phone = Phone(
            phone_number="+15051234567", phone_type="Mobile", contact_id=contact.id
        )
        session.add(phone)
        session.commit()
        session.refresh(phone)
        yield phone

        session.close()


@pytest.fixture(scope="session")
def asset():
    with session_ctx() as session:
        asset = Asset(
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

        session.close()


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
        session.close()


@pytest.fixture(scope="session")
def groundwater_level_observation(sensor, sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:04:00Z",
            sample_id=sample.id,
            sensor_id=sensor.id,
            observed_property="groundwater level:groundwater level",
            release_status="draft",
            value=10.0,
            unit="ft",
            measuring_point_height=5.0,
            level_status="normal",
        )
        session.add(observation)
        session.commit()
        yield observation

        session.close()


@pytest.fixture(scope="session")
def water_chemistry_observation(sensor, sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:03:00Z",
            sample_id=sample.id,
            sensor_id=sensor.id,
            observed_property="water chemistry:pH",
            release_status="draft",
            value=4.0,
            unit="dimensionless",
        )
        session.add(observation)
        session.commit()
        yield observation

        session.close()


@pytest.fixture(scope="session")
def geothermal_observation(sensor, sample):
    with session_ctx() as session:
        observation = Observation(
            observation_datetime="2025-01-01T00:02:00Z",
            sample_id=sample.id,
            sensor_id=sensor.id,
            observed_property="geothermal:temperature",
            release_status="draft",
            value=20.0,
            unit="deg C",
            observation_depth=200.0,
        )
        session.add(observation)
        session.commit()
        yield observation

        session.close()
