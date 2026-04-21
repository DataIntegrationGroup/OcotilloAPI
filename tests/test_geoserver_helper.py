from db import Asset
from services.geoserver_helper import GeoServerPublisher, publish_geotiff_asset

EXPECTED_MOUNTED_PATH = (
    "/mnt/geoserver-data/surveys/estancia_2025/aem/interpreted/depth_slices/"
    "estancia_2025_depth_050m.tif"
)
EXPECTED_EXTERNAL_GEOTIFF_URL = (
    "https://geoserver.test/geoserver/rest/workspaces/nmbgmr/coveragestores/"
    "estancia_2025_depth_050m/external.geotiff"
)


def _make_asset():
    return Asset(
        name="estancia_2025_depth_050m.tif",
        label="Estancia Depth Slice",
        storage_path=(
            "surveys/estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        ),
        storage_service="gcs",
        mime_type="image/tiff",
        size=123,
        uri=(
            "https://storage.cloud.google.com/mock-bucket/surveys/"
            "estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        ),
    )


def test_publish_geotiff_asset_creates_missing_store_and_layer(monkeypatch):
    class FakeGeoserverClient:
        def __init__(self):
            self.calls = []

        def get_workspace(self, workspace):
            self.calls.append(("get_workspace", workspace))
            raise RuntimeError("missing workspace")

        def create_workspace(self, workspace):
            self.calls.append(("create_workspace", workspace))
            return "201 workspace created"

        def get_coveragestore(self, coveragestore_name, workspace):
            self.calls.append(("get_coveragestore", coveragestore_name, workspace))
            return None

    put_calls = []

    class FakeResponse:
        status_code = 201
        text = "created"

    def fake_put(url, data, headers, auth, timeout):
        put_calls.append((url, data, headers, auth, timeout))
        return FakeResponse()

    client = FakeGeoserverClient()

    publisher = GeoServerPublisher(
        base_url="https://geoserver.test/geoserver",
        username="user",
        password="pass",
        geoserver_client=client,
    )

    monkeypatch.setenv("GEOSERVER_RASTER_SOURCE_ROOT", "/mnt/geoserver-data")
    monkeypatch.setattr("services.geoserver_helper.requests.put", fake_put)
    result = publish_geotiff_asset(_make_asset(), "estancia_2025", publisher=publisher)

    assert result.status == "success"
    assert ("create_workspace", "nmbgmr") in client.calls
    assert put_calls == [
        (
            EXPECTED_EXTERNAL_GEOTIFF_URL,
            EXPECTED_MOUNTED_PATH,
            {"Content-Type": "text/plain"},
            ("user", "pass"),
            publisher.timeout,
        )
    ]


def test_publish_geotiff_asset_is_idempotent_when_store_and_layer_exist(
    monkeypatch,
):
    class FakeGeoserverClient:
        def get_workspace(self, workspace):
            return {"workspace": workspace}

        def create_workspace(self, workspace):
            raise AssertionError("workspace should already exist")

        def get_coveragestore(self, coveragestore_name, workspace):
            return {"coverageStore": coveragestore_name}

    def fail_put(*args, **kwargs):
        raise AssertionError("external geotiff registration should not run")

    publisher = GeoServerPublisher(
        base_url="https://geoserver.test/geoserver",
        username="user",
        password="pass",
        geoserver_client=FakeGeoserverClient(),
    )

    monkeypatch.setattr("services.geoserver_helper.requests.put", fail_put)
    result = publish_geotiff_asset(_make_asset(), "estancia_2025", publisher=publisher)

    assert result.status == "success"
    assert result.detail == "GeoServer layer already exists."


def test_publish_geotiff_asset_records_failure_without_raising(monkeypatch):
    class FakeGeoserverClient:
        def get_workspace(self, workspace):
            raise RuntimeError("missing workspace")

        def create_workspace(self, workspace):
            return "201 workspace created"

        def get_coveragestore(self, coveragestore_name, workspace):
            return None

    class FakeResponse:
        status_code = 500
        text = "server exploded"

    def fake_put(url, data, headers, auth, timeout):
        assert data == EXPECTED_MOUNTED_PATH
        return FakeResponse()

    publisher = GeoServerPublisher(
        base_url="https://geoserver.test/geoserver",
        username="user",
        password="pass",
        geoserver_client=FakeGeoserverClient(),
    )

    monkeypatch.setenv("GEOSERVER_RASTER_SOURCE_ROOT", "/mnt/geoserver-data")
    monkeypatch.setattr("services.geoserver_helper.requests.put", fake_put)
    result = publish_geotiff_asset(_make_asset(), "estancia_2025", publisher=publisher)

    assert result.status == "failed"
    assert "status 500" in result.detail
    assert "server exploded" in result.detail


def test_publish_geotiff_asset_requires_local_source_root(monkeypatch):
    class FakeGeoserverClient:
        def get_workspace(self, workspace):
            return {"workspace": workspace}

        def get_coveragestore(self, coveragestore_name, workspace):
            return None

    def fail_put(*args, **kwargs):
        raise AssertionError("external geotiff registration should not be reached")

    publisher = GeoServerPublisher(
        base_url="https://geoserver.test/geoserver",
        username="user",
        password="pass",
        geoserver_client=FakeGeoserverClient(),
    )

    monkeypatch.delenv("GEOSERVER_RASTER_SOURCE_ROOT", raising=False)
    monkeypatch.setattr("services.geoserver_helper.requests.put", fail_put)
    result = publish_geotiff_asset(_make_asset(), "estancia_2025", publisher=publisher)

    assert result.status == "failed"
    assert "GEOSERVER_RASTER_SOURCE_ROOT" in result.detail
