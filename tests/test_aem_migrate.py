# flake8: noqa: E501
from pathlib import Path

from services.aem_migration import MigrationRunner


class FakeBlob:
    def __init__(self):
        self.uploaded_from = None
        self.md5_hash = "local-md5"

    def exists(self):
        return False

    def upload_from_filename(self, path):
        self.uploaded_from = path

    def reload(self):
        return None


class FakeBucket:
    def __init__(self):
        self.blobs = {}

    def blob(self, gcs_path):
        if gcs_path not in self.blobs:
            self.blobs[gcs_path] = FakeBlob()
        return self.blobs[gcs_path]


class FakeStorageClient:
    def __init__(self, bucket):
        self._bucket = bucket

    def bucket(self, _name):
        return self._bucket


def _mapping_csv(path: Path):
    path.write_text(
        (
            "survey_id,survey_folder,processing_stage,detected_type,action,"
            "normalization_needed,file_name,extension,size_human,size_bytes,"
            "source_path,proposed_gcs_path,normalization_notes,action_notes\n"
        ),
        encoding="utf-8",
    )


def test_upload_file_keeps_kmz_and_uploads_geopackage(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    _mapping_csv(mapping_path)
    bucket = FakeBucket()
    monkeypatch.setattr(
        "services.aem_migration.storage.Client",
        lambda: FakeStorageClient(bucket),
    )

    runner = MigrationRunner(
        mapping_path=str(mapping_path),
        bucket_name="example-bucket",
    )

    source = tmp_path / "flight_lines.kmz"
    source.write_bytes(b"kmz bytes")
    converted = tmp_path / "flight_lines.gpkg"
    converted.write_bytes(b"gpkg bytes")

    def fake_convert(_source_path):
        return str(converted)

    monkeypatch.setattr(runner, "_convert_kmz_to_geopackage", fake_convert)
    monkeypatch.setattr(runner, "_compute_md5", lambda _path: "local-md5")

    result = runner.upload_file(
        str(source), "surveys/estancia_2025/acquisition/vectors/flight_lines.kmz"
    )

    assert result.status == "uploaded"
    assert result.gcs_path.endswith(".kmz")
    assert bucket.blobs[result.gcs_path].uploaded_from == str(source)
    assert bucket.blobs[
        "surveys/estancia_2025/acquisition/vectors/flight_lines.gpkg"
    ].uploaded_from == str(converted)
    assert not converted.exists()


def test_upload_file_reports_kmz_conversion_failure(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    _mapping_csv(mapping_path)
    monkeypatch.setattr(
        "services.aem_migration.storage.Client",
        lambda: FakeStorageClient(FakeBucket()),
    )

    runner = MigrationRunner(
        mapping_path=str(mapping_path),
        bucket_name="example-bucket",
    )

    source = tmp_path / "flight_lines.kmz"
    source.write_bytes(b"kmz bytes")

    monkeypatch.setattr(
        runner,
        "_convert_kmz_to_geopackage",
        lambda _source_path: (_ for _ in ()).throw(RuntimeError("geopandas missing")),
    )

    result = runner.upload_file(
        str(source), "surveys/estancia_2025/acquisition/vectors/flight_lines.kmz"
    )

    assert result.status == "uploaded"
    assert result.gcs_path.endswith(".kmz")
    assert any(r.status == "failed" for r in runner.results)
    assert "geopandas missing" in runner.results[0].error_message
