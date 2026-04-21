import io

from db import Asset
from services.aem_asset_ingest import (
    AEMIngestRecord,
    ingest_validated_aem_asset,
)
from services.geoserver_helper import PublishResult
from services.gcs_helper import make_blob_uri
from db.engine import session_ctx
from starlette.datastructures import UploadFile


class MockBlob:
    def upload_from_file(self, *args, **kwargs):
        return None


class MockBucket:
    name = "mock-bucket"

    def __init__(self):
        self.existing = {}

    def get_blob(self, blob_name, timeout=None):
        return self.existing.get(blob_name)

    def blob(self, blob_name):
        self.existing[blob_name] = MockBlob()
        return self.existing[blob_name]


def _upload(name: str = "estancia_2025_depth_050m.tif") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"geotiff-bytes"),
        filename=name,
        size=len(b"geotiff-bytes"),
        headers={"content-type": "image/tiff"},
    )


def _record(**overrides) -> AEMIngestRecord:
    base = AEMIngestRecord(
        survey_id="estancia_2025",
        file_name="estancia_2025_depth_050m.tif",
        proposed_gcs_path=(
            "surveys/estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        ),
        action="MOVE",
        normalization_needed=False,
        detected_type="geotiff",
        processing_stage="interpreted",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_ingest_validated_aem_asset_uploads_and_publishes(monkeypatch):
    bucket = MockBucket()
    published = {}

    def fake_publish(asset, survey_id, workspace="nmbgmr", publisher=None):
        published["asset_id"] = asset.id
        published["survey_id"] = survey_id
        return PublishResult(
            target="geoserver",
            status="success",
            workspace=workspace,
            store_name="estancia_store",
            layer_name="estancia_layer",
        )

    monkeypatch.setattr(
        "services.aem_asset_ingest.publish_geotiff_asset",
        fake_publish,
    )

    with session_ctx() as session:
        result = ingest_validated_aem_asset(
            session,
            _upload(),
            _record(),
            bucket=bucket,
        )
        session.commit()
        asset_id = result.asset.id

    with session_ctx() as session:
        asset = session.get(Asset, asset_id)
        assert asset.storage_path == _record().proposed_gcs_path
        assert asset.uri == make_blob_uri(
            bucket.name,
            _record().proposed_gcs_path,
        )
        assert asset.publish_status == "success"
        assert asset.publish_store_name == "estancia_store"
        assert published["survey_id"] == "estancia_2025"
        session.delete(asset)
        session.commit()


def test_ingest_validated_aem_asset_fails_best_effort(monkeypatch):
    bucket = MockBucket()

    def fake_publish(asset, survey_id, workspace="nmbgmr", publisher=None):
        return PublishResult(
            target="geoserver",
            status="failed",
            workspace=workspace,
            store_name="estancia_store",
            layer_name="estancia_layer",
            detail="bad gateway",
        )

    monkeypatch.setattr(
        "services.aem_asset_ingest.publish_geotiff_asset",
        fake_publish,
    )

    with session_ctx() as session:
        result = ingest_validated_aem_asset(
            session,
            _upload(),
            _record(),
            bucket=bucket,
        )
        session.commit()
        asset_id = result.asset.id
        assert result.asset.id is not None
        assert result.published is False

    with session_ctx() as session:
        asset = session.get(Asset, asset_id)
        assert asset.publish_status == "failed"
        assert asset.publish_last_error == "bad gateway"
        session.delete(asset)
        session.commit()


def test_ingest_validated_aem_asset_skips_non_ingestable_geotiff(monkeypatch):
    bucket = MockBucket()

    def fail_publish(*args, **kwargs):
        raise AssertionError("publish should not be called")

    monkeypatch.setattr(
        "services.aem_asset_ingest.publish_geotiff_asset",
        fail_publish,
    )

    with session_ctx() as session:
        result = ingest_validated_aem_asset(
            session,
            _upload(),
            _record(action="HOLD"),
            bucket=bucket,
        )
        session.commit()
        asset_id = result.asset.id
        assert result.publish_result.status == "skipped"

    with session_ctx() as session:
        asset = session.get(Asset, asset_id)
        assert asset.publish_status == "skipped"
        session.delete(asset)
        session.commit()


def test_ingest_validated_aem_asset_reuses_existing_asset(monkeypatch):
    bucket = MockBucket()
    publish_calls = []

    def fake_publish(asset, survey_id, workspace="nmbgmr", publisher=None):
        publish_calls.append(asset.id)
        return PublishResult(
            target="geoserver",
            status="success",
            workspace=workspace,
            store_name="estancia_store",
            layer_name="estancia_layer",
        )

    monkeypatch.setattr(
        "services.aem_asset_ingest.publish_geotiff_asset",
        fake_publish,
    )

    with session_ctx() as session:
        first = ingest_validated_aem_asset(
            session,
            _upload(),
            _record(),
            bucket=bucket,
        )
        session.commit()
        first_id = first.asset.id

    with session_ctx() as session:
        second = ingest_validated_aem_asset(
            session,
            _upload(),
            _record(),
            bucket=bucket,
        )
        session.commit()
        second_id = second.asset.id

    assert first_id == second_id
    assert publish_calls == [first_id, first_id]

    with session_ctx() as session:
        asset = session.get(Asset, first_id)
        session.delete(asset)
        session.commit()


def test_ingest_validated_aem_asset_can_skip_db_persistence(monkeypatch):
    bucket = MockBucket()
    published = {}

    def fake_publish(asset, survey_id, workspace="nmbgmr", publisher=None):
        published["asset_id"] = asset.id
        published["storage_path"] = asset.storage_path
        published["survey_id"] = survey_id
        return PublishResult(
            target="geoserver",
            status="success",
            workspace=workspace,
            store_name="estancia_store",
            layer_name="estancia_layer",
        )

    monkeypatch.setattr(
        "services.aem_asset_ingest.publish_geotiff_asset",
        fake_publish,
    )

    result = ingest_validated_aem_asset(
        None,
        _upload(),
        _record(),
        bucket=bucket,
        persist_asset_metadata=False,
    )

    assert result.asset.id is None
    assert result.asset.storage_path == _record().proposed_gcs_path
    assert result.publish_result.status == "success"
    assert published["asset_id"] is None
    assert published["survey_id"] == "estancia_2025"
