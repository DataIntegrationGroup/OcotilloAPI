# flake8: noqa: E501
from __future__ import annotations

from pathlib import Path

import csv
import datetime
import pandas as pd
from cli.cli import cli
from db.engine import engine
from schemas.aem import IngestConfig, InversionCode, ProcessingStage, SourceFormat
from services import aem_ingest as aem_ingest_service
from services import aem_stac as aem_stac_service
from services.aem_batch import run_batch
from services.aem_parsers import (
    detect_format,
    parse_agf_lci,
    parse_bylayer,
    parse_seogi_rho,
)
from sqlalchemy import inspect
from typer.testing import CliRunner


def test_aem_top_level_imports_and_tables_exist():
    import db.aem  # noqa: F401
    import schemas.aem  # noqa: F401
    import services.aem_ingest  # noqa: F401

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert "aem_soundings" in table_names
    assert "aem_sounding_metadata" in table_names


def test_cli_registers_aem_group():
    runner = CliRunner()
    result = runner.invoke(cli, ["aem-ingest", "--help"])

    assert result.exit_code == 0, result.output
    assert "aem-ingest" in result.output
    assert "run" in result.output
    assert "batch" in result.output


def test_detect_and_parse_bylayer(tmp_path: Path):
    filepath = tmp_path / "sample_byLayer.xyz"
    filepath.write_text(
        "/ ID LINE_NO LAYER_NO UTMX UTMY ELEVATION_CELL DEPTH_TOP DEPTH_BOTTOM THICKNESS RESISTIVITY\n"
        "1 10 1 500000 3800000 1500 0 10 10 100\n",
        encoding="utf-8",
    )

    assert detect_format(str(filepath)) == SourceFormat.BYLAYER
    df = parse_bylayer(str(filepath))

    assert len(df) == 1
    assert set(["line_id", "record_id", "resistivity"]).issubset(df.columns)
    assert df.iloc[0]["record_id"] == "1"


def test_detect_and_parse_seogi(tmp_path: Path):
    filepath = tmp_path / "rho_GL250193_F02.csv"
    pd.DataFrame(
        [
            {
                "record": 1,
                "line_no": "L1",
                "utmx": 500000,
                "utmy": 3800000,
                "elevation": 1500,
                "top_1_layer_m": 0,
                "bottom_1_layer_m": 10,
                "rho_1_layer_m": 100,
            }
        ]
    ).to_csv(filepath, index=False)

    assert detect_format(str(filepath)) == SourceFormat.SEOGI_RHO
    df = parse_seogi_rho(str(filepath))

    assert len(df) == 1
    assert df.iloc[0]["record_id"] == "F02_1"
    assert df.iloc[0]["source_epsg"] == 32613


def test_detect_and_parse_agf(tmp_path: Path):
    filepath = tmp_path / "agf_prelim_306.csv"
    pd.DataFrame(
        [
            {
                "Line": "L1",
                "E_UTM13Nm": 500000,
                "N_UTM13Nm": 3800000,
                "DEM_m": 1500,
                "RHO[0]": 100,
                "DEP_TOP_m[0]": 0,
                "DEP_BOT_m[0]": 10,
            }
        ]
    ).to_csv(filepath, index=False)

    assert detect_format(str(filepath)) == SourceFormat.AGF_LCI
    df = parse_agf_lci(str(filepath), system="306hp")

    assert len(df) == 1
    assert df.iloc[0]["layer_no"] == 1
    assert df.iloc[0]["source_epsg"] == 26913


def test_run_ingest_dispatches_parser_and_writers(monkeypatch, tmp_path: Path):
    filepath = tmp_path / "rho_GL250193_F02.csv"
    filepath.write_text("placeholder", encoding="utf-8")

    parsed_df = pd.DataFrame(
        [
            {
                "record_id": "F02_1",
                "line_id": "L1",
                "layer_no": 1,
                "easting": 500000,
                "northing": 3800000,
                "depth_top": 0,
                "depth_bot": 10,
                "resistivity": 100,
                "source_epsg": 32613,
            }
        ]
    )

    called = {"parse": 0, "load": 0}

    monkeypatch.setattr(
        aem_ingest_service, "detect_format", lambda _path: SourceFormat.SEOGI_RHO
    )

    def fake_parse(_path, flight_id=None):
        called["parse"] += 1
        return parsed_df.copy()

    monkeypatch.setattr(aem_ingest_service, "parse_seogi_rho", fake_parse)
    monkeypatch.setattr(
        aem_ingest_service,
        "load_to_postgis",
        lambda df, config: called.__setitem__("load", len(df)) or len(df),
    )
    monkeypatch.setattr(
        aem_ingest_service,
        "write_parquet",
        lambda df, config, gcs_client: "surveys/test/aem/file.parquet",
    )
    monkeypatch.setattr(
        aem_ingest_service,
        "write_raw_manifest",
        lambda *args, **kwargs: "surveys/test/metadata/raw_files.json",
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "write_stac_payloads",
        lambda collection, items, config, gcs_client, ensure_prefix_readmes: {
            "collection_gcs_path": "surveys/test/metadata/stac/collection.json",
            "items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
        },
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "load_stac_to_pgstac",
        lambda collection, items: None,
    )

    class FakeStorageClient:
        pass

    monkeypatch.setattr(
        aem_ingest_service.storage, "Client", lambda: FakeStorageClient()
    )

    config = IngestConfig(
        filepath=str(filepath),
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
    )

    result = aem_ingest_service.run_ingest(config)

    assert result == {
        "survey_id": "gila_animas_2025",
        "processing_stage": "preliminary_inversion",
        "inversion_code": "seogi_python",
        "source_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
        "parquet_gcs_path": "surveys/test/aem/file.parquet",
        "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
        "stac_collection_id": "aem-gila_animas_2025",
        "stac_item_count": 1,
        "stac_collection_gcs_path": "surveys/test/metadata/stac/collection.json",
        "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
        "rows_loaded": 1,
    }
    assert called["parse"] == 1
    assert called["load"] == 1


def test_run_batch_dry_run_without_db_conn(tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    with mapping_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "survey_id",
                "detected_type",
                "action",
                "processing_stage",
                "file_name",
                "source_path",
                "proposed_gcs_path",
                "size_bytes",
                "size_human",
                "normalization_needed",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "survey_id": "gila_animas_2025",
                "detected_type": "seogi_rho",
                "action": "MOVE",
                "processing_stage": "preliminary_inversion",
                "file_name": "rho_GL250193_F02.csv",
                "source_path": "/tmp/rho_GL250193_F02.csv",
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        dry_run=True,
    )

    assert result == []


def test_build_stac_payloads_are_deterministic():
    df = pd.DataFrame(
        [
            {
                "line_id": "L2",
                "record_id": "R2",
                "easting": 500100,
                "northing": 3800100,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 2),
            },
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 1),
            },
        ]
    )
    config = IngestConfig(
        filepath="/tmp/input.csv",
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/source.csv",
    )

    collection = aem_stac_service.build_stac_collection(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )
    items = aem_stac_service.build_stac_items(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert collection["id"] == "aem-gila_animas_2025"
    assert collection["extent"]["temporal"]["interval"] == [
        [
            "2025-03-01T00:00:00Z",
            "2025-03-02T00:00:00Z",
        ]
    ]
    assert (
        collection["assets"]["parquet"]["href"]
        == "gs://example-bucket/surveys/gila_animas_2025/out.parquet"
    )
    assert [item["id"] for item in items] == [
        "aem-gila_animas_2025-preliminary_inversion-L1-R1",
        "aem-gila_animas_2025-preliminary_inversion-L2-R2",
    ]
    assert items[0]["properties"]["datetime"] == "2025-03-01T00:00:00Z"
    assert items[1]["properties"]["datetime"] == "2025-03-02T00:00:00Z"


def test_load_stac_to_pgstac_uses_upsert(monkeypatch):
    calls = []

    class FakeMethods:
        upsert = "upsert"

    class FakeDB:
        def __init__(self, dsn):
            self.dsn = dsn

        def disconnect(self):
            calls.append(("disconnect", self.dsn))

    class FakeLoader:
        def __init__(self, db):
            self.db = db

        def load_collections(self, file, insert_mode):
            calls.append(("collections", list(file), insert_mode))

        def load_items(self, file, insert_mode, chunksize):
            calls.append(("items", list(file), insert_mode, chunksize))

    monkeypatch.setattr(
        aem_stac_service,
        "_import_pypgstac",
        lambda: (FakeDB, FakeLoader, FakeMethods),
    )
    monkeypatch.setattr(
        aem_stac_service,
        "_build_pgstac_dsn",
        lambda: "postgresql://example",
    )

    collection = {"id": "aem-gila_animas_2025"}
    items = [{"id": "item-1", "collection": "aem-gila_animas_2025"}]

    aem_stac_service.load_stac_to_pgstac(collection, items)

    assert calls == [
        ("collections", [collection], "upsert"),
        ("items", items, "upsert", 1000),
        ("disconnect", "postgresql://example"),
    ]


def test_ensure_prefix_readmes_creates_all_parent_directory_readmes():
    class FakeBlob:
        def __init__(self, path, store):
            self.path = path
            self.store = store

        def exists(self):
            return self.path in self.store

        def upload_from_string(self, content, content_type=None):
            self.store[self.path] = {
                "content": content,
                "content_type": content_type,
            }

    class FakeBucket:
        def __init__(self):
            self.store = {}

        def blob(self, path):
            return FakeBlob(path, self.store)

    class FakeClient:
        def __init__(self, bucket):
            self._bucket = bucket

        def bucket(self, _name):
            return self._bucket

    bucket = FakeBucket()
    client = FakeClient(bucket)

    created = aem_ingest_service.ensure_prefix_readmes(
        "example-bucket",
        client,
        [
            "surveys/gila_animas_2025/aem/inversion/preliminary/parquet/output.parquet",
            "surveys/gila_animas_2025/metadata/raw_files.json",
        ],
    )

    expected = {
        "surveys/README.md",
        "surveys/gila_animas_2025/README.md",
        "surveys/gila_animas_2025/aem/README.md",
        "surveys/gila_animas_2025/aem/inversion/README.md",
        "surveys/gila_animas_2025/aem/inversion/preliminary/README.md",
        "surveys/gila_animas_2025/aem/inversion/preliminary/parquet/README.md",
        "surveys/gila_animas_2025/metadata/README.md",
    }

    assert set(created) == expected
    assert set(bucket.store) == expected
    assert (
        bucket.store["surveys/gila_animas_2025/metadata/README.md"]["content_type"]
        == "text/markdown"
    )
