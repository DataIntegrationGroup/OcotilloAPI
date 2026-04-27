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
from services.aem_parsers.common import finalize_parsed_dataframe
from sqlalchemy import inspect
from typer.testing import CliRunner


def _fake_migration_runner(monkeypatch, captured=None):
    captured = captured if captured is not None else {}

    class FakeMigrationRunner:
        def __init__(self, mapping_path, bucket_name, root_override=None):
            self.mapping_path = mapping_path
            self.bucket_name = bucket_name
            self.root_override = root_override
            self.df = pd.read_csv(mapping_path)
            self.results = []
            self.failed_rows = []

        def get_filtered_rows(
            self,
            survey_filter=None,
            stage_filter=None,
            limit=None,
        ):
            df = self.df.copy()
            if survey_filter:
                df = df[df["survey_id"] == survey_filter]
            if stage_filter:
                df = df[df["processing_stage"] == stage_filter]
            if limit is not None:
                df = df.head(limit)
            return df

        def run(
            self,
            dry_run=False,
            survey_filter=None,
            stage_filter=None,
            workers=4,
            limit=None,
        ):
            captured["dry_run"] = dry_run
            captured["survey_filter"] = survey_filter
            captured["stage_filter"] = stage_filter
            captured["workers"] = workers
            captured["limit"] = limit
            filtered = self.get_filtered_rows(survey_filter, stage_filter, limit)
            self.results = [
                type(
                    "Result",
                    (),
                    {
                        "gcs_path": row["proposed_gcs_path"],
                        "status": "uploaded",
                    },
                )()
                for _, row in filtered[filtered["action"] == "MOVE"].iterrows()
            ]

        def write_outputs(self):
            captured["write_outputs"] = True

        def resolve_source_path(self, source_path):
            return source_path

    monkeypatch.setattr("services.aem_batch.MigrationRunner", FakeMigrationRunner)
    return captured


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
    assert df.iloc[0]["source_epsg"] == 26913


def test_parse_seogi_respects_source_epsg_override(tmp_path: Path):
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

    df = parse_seogi_rho(str(filepath), source_epsg=32612)

    assert len(df) == 1
    assert df.iloc[0]["source_epsg"] == 26913


def test_resolve_seogi_source_epsg_uses_zone_12_for_gila_animas():
    assert aem_ingest_service._resolve_seogi_source_epsg("gila_animas_2025") == 32612
    assert aem_ingest_service._resolve_seogi_source_epsg("estancia_2025") == 32613


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

    def fake_parse(_path, flight_id=None, source_epsg=32613):
        called["parse"] += 1
        called["source_epsg"] = source_epsg
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
        lambda collections, items, config, gcs_client, ensure_prefix_readmes: {
            "collection_gcs_path": "surveys/test/metadata/stac/inversion_collection.json",
            "items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "collection_gcs_paths": {
                "raw": "surveys/test/metadata/stac/raw_collection.json",
                "inversion": "surveys/test/metadata/stac/inversion_collection.json",
            },
        },
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "load_stac_to_pgstac",
        lambda collections, items: None,
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
        "stac_collection_id": "aem-gila_animas_2025-preliminary_inversion-seogi_python",
        "stac_raw_collection_id": "aem-gila_animas_2025-raw",
        "stac_item_count": 1,
        "stac_debug_limit_applied": False,
        "stac_collection_gcs_path": "surveys/test/metadata/stac/inversion_collection.json",
        "stac_collection_gcs_paths": {
            "raw": "surveys/test/metadata/stac/raw_collection.json",
            "inversion": "surveys/test/metadata/stac/inversion_collection.json",
        },
        "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
        "rows_loaded": 1,
    }
    assert called["parse"] == 1
    assert called["load"] == 1
    assert called["source_epsg"] == 32612


def test_run_ingest_can_skip_stac_uploads(monkeypatch, tmp_path: Path):
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

    monkeypatch.setattr(
        aem_ingest_service, "detect_format", lambda _path: SourceFormat.SEOGI_RHO
    )
    monkeypatch.setattr(
        aem_ingest_service,
        "parse_seogi_rho",
        lambda _path, flight_id=None, source_epsg=32613: parsed_df.copy(),
    )
    monkeypatch.setattr(
        aem_ingest_service, "load_to_postgis", lambda df, config: len(df)
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
        "build_stac_collection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("STAC collection should not be built")
        ),
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "build_stac_items",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("STAC items should not be built")
        ),
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "write_stac_payloads",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("STAC payloads should not be written")
        ),
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "load_stac_to_pgstac",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("pgstac load should not run")
        ),
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

    result = aem_ingest_service.run_ingest(config, skip_stac_uploads=True)

    assert result["stac_collection_id"] is None
    assert result["stac_raw_collection_id"] is None
    assert result["stac_item_count"] == 0
    assert result["stac_debug_limit_applied"] is False
    assert result["stac_collection_gcs_path"] is None
    assert result["stac_collection_gcs_paths"] == {}
    assert result["stac_items_gcs_path"] is None


def test_load_to_postgis_batches_and_truncates_staging(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "record_id": f"R{i}",
                "line_id": "L1",
                "layer_no": 1,
                "easting": 500000 + i,
                "northing": 3800000 + i,
                "elevation": 1500.0,
                "sensor_alt": 40.0,
                "terrain_clear": 5.0,
                "depth_top": 0.0,
                "depth_bot": 10.0,
                "thickness": 10.0,
                "resistivity": 100.0,
                "resistivity_std": 1.0,
                "conductivity": 0.01,
                "doi_conservative": 50.0,
                "doi_standard": 60.0,
                "resdata": 1.0,
                "restotal": 2.0,
                "plni": 3.0,
                "date_acquired": datetime.date(2025, 1, 1),
                "source_epsg": 26913,
            }
            for i in range(5)
        ]
    )

    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.rowcount = 0
            self.copy_rows = []
            self.insert_rowcounts = [2, 2, 1]

        def execute(self, sql, stream=None):
            self.calls.append(sql.strip())
            if hasattr(stream, "getvalue"):
                payload = stream.getvalue().strip().splitlines()
                if "COPY _ingest_staging" in sql:
                    self.copy_rows.append(len([line for line in payload if line]))
                return
            if "INSERT INTO aem_soundings" in sql:
                self.rowcount = self.insert_rowcounts.pop(0)

        def close(self):
            pass

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.commit_count = 0
            self.rolled_back = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commit_count += 1

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    raw_conn = FakeConnection()

    metadata_batches = []

    monkeypatch.setenv("AEM_POSTGIS_COPY_BATCH_SIZE", "2")
    monkeypatch.setattr(aem_ingest_service, "get_raw_connection", lambda: raw_conn)
    monkeypatch.setattr(
        aem_ingest_service,
        "_insert_metadata",
        lambda cur, survey_id, processing_stage, inversion_code, batch_df: metadata_batches.append(
            len(batch_df)
        ),
    )

    config = IngestConfig(
        filepath="/tmp/example.csv",
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/aem/inversion/preliminary/example.csv",
    )

    row_count = aem_ingest_service.load_to_postgis(df, config)

    assert row_count == 5
    assert raw_conn.commit_count == 3
    assert raw_conn.rolled_back is False
    assert raw_conn.cursor_obj.copy_rows == [2, 2, 1]
    assert metadata_batches == [2, 2, 1]
    assert raw_conn.cursor_obj.calls.count("TRUNCATE _ingest_staging;") == 3


def test_run_batch_dry_run_without_db_conn(monkeypatch, tmp_path: Path):
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

    captured = _fake_migration_runner(monkeypatch)

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        dry_run=True,
    )

    assert result == []
    assert captured["dry_run"] is True


def test_run_batch_skips_soundings_upload_by_default(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")

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
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    captured: dict[str, object] = {}
    migration_captured = _fake_migration_runner(monkeypatch)

    def fake_run_ingest(
        config,
        raw_file_paths=None,
        acquisition_file_paths=None,
        raw_manifest_notes="",
        skip_soundings_upload=True,
        skip_stac_uploads=False,
        debug_stac_limit=False,
        debug_stac_remaining_by_collection=None,
    ):
        captured["skip_soundings_upload"] = skip_soundings_upload
        captured["source_gcs_path"] = config.source_gcs_path
        captured["acquisition_file_paths"] = acquisition_file_paths
        return {
            "survey_id": config.survey_id,
            "processing_stage": config.processing_stage.value,
            "inversion_code": config.inversion_code.value,
            "source_gcs_path": config.source_gcs_path,
            "parquet_gcs_path": "surveys/test/aem/file.parquet",
            "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
            "stac_collection_id": "aem-gila_animas_2025",
            "stac_item_count": 1,
            "stac_collection_gcs_path": "surveys/test/metadata/stac/collection.json",
            "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "rows_loaded": 0,
        }

    monkeypatch.setattr("services.aem_ingest.run_ingest", fake_run_ingest)

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
    )

    assert len(result) == 1
    assert captured["skip_soundings_upload"] is True
    assert migration_captured["write_outputs"] is True
    assert (
        captured["source_gcs_path"]
        == "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv"
    )
    assert captured["acquisition_file_paths"] == []


def test_run_batch_passes_upload_soundings_opt_in(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")

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
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    captured: dict[str, object] = {}
    _fake_migration_runner(monkeypatch)

    def fake_run_ingest(
        config,
        raw_file_paths=None,
        acquisition_file_paths=None,
        raw_manifest_notes="",
        skip_soundings_upload=True,
        skip_stac_uploads=False,
        debug_stac_limit=False,
        debug_stac_remaining_by_collection=None,
    ):
        captured["skip_soundings_upload"] = skip_soundings_upload
        return {
            "survey_id": config.survey_id,
            "processing_stage": config.processing_stage.value,
            "inversion_code": config.inversion_code.value,
            "source_gcs_path": config.source_gcs_path,
            "parquet_gcs_path": "surveys/test/aem/file.parquet",
            "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
            "stac_collection_id": "aem-gila_animas_2025",
            "stac_item_count": 1,
            "stac_collection_gcs_path": "surveys/test/metadata/stac/collection.json",
            "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "rows_loaded": 0,
        }

    monkeypatch.setattr("services.aem_ingest.run_ingest", fake_run_ingest)

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        skip_soundings_upload=False,
    )

    assert len(result) == 1
    assert captured["skip_soundings_upload"] is False


def test_run_batch_passes_skip_stac_uploads(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")

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
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    captured: dict[str, object] = {}
    _fake_migration_runner(monkeypatch)

    def fake_run_ingest(
        config,
        raw_file_paths=None,
        acquisition_file_paths=None,
        raw_manifest_notes="",
        skip_soundings_upload=False,
        skip_stac_uploads=False,
        debug_stac_limit=False,
        debug_stac_remaining_by_collection=None,
    ):
        captured["skip_stac_uploads"] = skip_stac_uploads
        return {
            "survey_id": config.survey_id,
            "processing_stage": config.processing_stage.value,
            "inversion_code": config.inversion_code.value,
            "source_gcs_path": config.source_gcs_path,
            "parquet_gcs_path": "surveys/test/aem/file.parquet",
            "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
            "stac_collection_id": None,
            "stac_item_count": 0,
            "stac_collection_gcs_path": None,
            "stac_items_gcs_path": None,
            "rows_loaded": 0,
        }

    monkeypatch.setattr("services.aem_ingest.run_ingest", fake_run_ingest)

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        skip_stac_uploads=True,
    )

    assert len(result) == 1
    assert captured["skip_stac_uploads"] is True


def test_run_batch_passes_debug_stac_limit(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")

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
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    captured: dict[str, object] = {}
    _fake_migration_runner(monkeypatch)

    def fake_run_ingest(
        config,
        raw_file_paths=None,
        acquisition_file_paths=None,
        raw_manifest_notes="",
        skip_soundings_upload=False,
        skip_stac_uploads=False,
        debug_stac_limit=False,
        debug_stac_remaining_by_collection=None,
    ):
        captured["debug_stac_limit"] = debug_stac_limit
        captured["debug_stac_remaining_by_collection"] = (
            debug_stac_remaining_by_collection
        )
        return {
            "survey_id": config.survey_id,
            "processing_stage": config.processing_stage.value,
            "inversion_code": config.inversion_code.value,
            "source_gcs_path": config.source_gcs_path,
            "parquet_gcs_path": "surveys/test/aem/file.parquet",
            "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
            "stac_collection_id": "aem-gila_animas_2025-preliminary_inversion-seogi_python",
            "stac_raw_collection_id": "aem-gila_animas_2025-raw",
            "stac_item_count": 1000,
            "stac_debug_limit_applied": True,
            "stac_collection_gcs_path": "surveys/test/metadata/stac/inversion_collection.json",
            "stac_collection_gcs_paths": {
                "raw": "surveys/test/metadata/stac/raw_collection.json",
                "inversion": "surveys/test/metadata/stac/inversion_collection.json",
            },
            "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "rows_loaded": 0,
        }

    monkeypatch.setattr("services.aem_ingest.run_ingest", fake_run_ingest)

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        debug_stac_limit=True,
    )

    assert len(result) == 1
    assert captured["debug_stac_limit"] is True
    assert captured["debug_stac_remaining_by_collection"] == {}


def test_run_batch_processes_geotiff_assets(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "estancia_2025_depth_050m.tif"
    source_path.write_bytes(b"fake-geotiff")

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
                "survey_id": "estancia_2025",
                "detected_type": "geotiff",
                "action": "MOVE",
                "processing_stage": "interpreted",
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/estancia_2025/aem/interpreted/depth_slices/estancia_2025_depth_050m.tif",
                "size_bytes": "12",
                "size_human": "12 B",
                "normalization_needed": "Y",
            }
        )

    _fake_migration_runner(monkeypatch)

    class FakeSession:
        def commit(self):
            return None

    captured: dict[str, object] = {}

    class FakeSessionCtx:
        def __enter__(self):
            return FakeSession()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeBucket:
        name = "example-bucket"

    class FakeAsset:
        id = 42
        name = "estancia_2025_depth_050m.tif"
        storage_path = (
            "surveys/estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        )
        uri = (
            "https://storage.cloud.google.com/example-bucket/surveys/"
            "estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        )

    class FakePublishResult:
        target = "geoserver"
        status = "success"
        workspace = "nmbgmr"
        store_name = "estancia_2025_depth_050m"
        layer_name = "estancia_2025_depth_050m"
        detail = None

    class FakeAssetResult:
        asset = FakeAsset()
        publish_result = FakePublishResult()

    def fake_ingest_validated_aem_asset(
        session, upload, record, bucket=None, workspace="nmbgmr"
    ):
        captured["filename"] = upload.filename
        captured["survey_id"] = record.survey_id
        captured["normalization_needed"] = record.normalization_needed
        captured["bucket_name"] = bucket.name if bucket else None
        return FakeAssetResult()

    monkeypatch.setattr("db.engine.session_ctx", FakeSessionCtx)
    monkeypatch.setattr(
        "services.aem_asset_ingest.ingest_validated_aem_asset",
        fake_ingest_validated_aem_asset,
    )
    monkeypatch.setattr(
        "services.gcs_helper.get_storage_bucket",
        lambda client=None, bucket=None: FakeBucket(),
    )

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
    )

    assert len(result) == 1
    assert result[0]["publish_status"] == "success"
    assert captured["filename"] == "estancia_2025_depth_050m.tif"
    assert captured["survey_id"] == "estancia_2025"
    assert captured["normalization_needed"] is True
    assert captured["bucket_name"] == "example-bucket"


def test_run_batch_processes_geotiff_assets_without_db_publish(
    monkeypatch, tmp_path: Path
):
    mapping_path = tmp_path / "mapping.csv"
    source_path = tmp_path / "estancia_2025_depth_050m.tif"
    source_path.write_bytes(b"fake-geotiff")

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
                "survey_id": "estancia_2025",
                "detected_type": "geotiff",
                "action": "MOVE",
                "processing_stage": "interpreted",
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/estancia_2025/aem/interpreted/depth_slices/estancia_2025_depth_050m.tif",
                "size_bytes": "12",
                "size_human": "12 B",
                "normalization_needed": "Y",
            }
        )

    captured: dict[str, object] = {}
    _fake_migration_runner(monkeypatch)

    class FakeBucket:
        name = "example-bucket"

    class FakeAsset:
        id = None
        name = "estancia_2025_depth_050m.tif"
        storage_path = (
            "surveys/estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        )
        uri = (
            "https://storage.cloud.google.com/example-bucket/surveys/"
            "estancia_2025/aem/interpreted/depth_slices/"
            "estancia_2025_depth_050m.tif"
        )

    class FakePublishResult:
        target = "geoserver"
        status = "success"
        workspace = "nmbgmr"
        store_name = "estancia_2025_depth_050m"
        layer_name = "estancia_2025_depth_050m"
        detail = None

    class FakeAssetResult:
        asset = FakeAsset()
        publish_result = FakePublishResult()

    def fake_ingest_validated_aem_asset(
        session,
        upload,
        record,
        bucket=None,
        workspace="nmbgmr",
        persist_asset_metadata=True,
    ):
        captured["session"] = session
        captured["persist_asset_metadata"] = persist_asset_metadata
        captured["filename"] = upload.filename
        return FakeAssetResult()

    monkeypatch.setattr(
        "services.aem_asset_ingest.ingest_validated_aem_asset",
        fake_ingest_validated_aem_asset,
    )
    monkeypatch.setattr(
        "services.gcs_helper.get_storage_bucket",
        lambda client=None, bucket=None: FakeBucket(),
    )

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
        skip_asset_db_publish=True,
    )

    assert len(result) == 1
    assert result[0]["asset_db_publish_skipped"] is True
    assert result[0]["asset_id"] is None
    assert captured["session"] is None
    assert captured["persist_asset_metadata"] is False


def test_run_batch_runs_shared_migration_for_kmz_rows(monkeypatch, tmp_path: Path):
    mapping_path = tmp_path / "mapping.csv"
    kmz_path = tmp_path / "flight_lines.kmz"
    kmz_path.write_bytes(b"kmz-bytes")
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")

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
                "detected_type": "kmz",
                "action": "MOVE",
                "processing_stage": "acquisition_metadata",
                "file_name": kmz_path.name,
                "source_path": str(kmz_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/acquisition/vectors/flight_lines.kmz",
                "size_bytes": "9",
                "size_human": "9 B",
                "normalization_needed": "N",
            }
        )
        writer.writerow(
            {
                "survey_id": "gila_animas_2025",
                "detected_type": "seogi_rho",
                "action": "MOVE",
                "processing_stage": "preliminary_inversion",
                "file_name": source_path.name,
                "source_path": str(source_path),
                "proposed_gcs_path": "surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
                "size_bytes": "100",
                "size_human": "100 B",
                "normalization_needed": "N",
            }
        )

    migration_captured: dict[str, object] = {}
    _fake_migration_runner(monkeypatch, migration_captured)

    monkeypatch.setattr(
        "services.aem_ingest.run_ingest",
        lambda config, **kwargs: {
            "survey_id": config.survey_id,
            "processing_stage": config.processing_stage.value,
            "inversion_code": config.inversion_code.value,
            "source_gcs_path": config.source_gcs_path,
            "parquet_gcs_path": "surveys/test/aem/file.parquet",
            "raw_manifest_gcs_path": "surveys/test/metadata/raw_files.json",
            "stac_collection_id": "aem-gila_animas_2025",
            "stac_item_count": 1,
            "stac_collection_gcs_path": "surveys/test/metadata/stac/collection.json",
            "stac_items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "rows_loaded": 0,
        },
    )

    result = run_batch(
        mapping_path=str(mapping_path),
        gcs_bucket="example-bucket",
    )

    assert len(result) == 1
    assert result[0]["source_gcs_path"].endswith("rho_GL250193_F02.csv")
    assert migration_captured["write_outputs"] is True


def test_apply_acquisition_metadata_timestamps_joins_by_line_and_point_order(
    tmp_path: Path,
):
    acquisition_path = tmp_path / "raw_GL250193_F02.csv"
    acquisition_path.write_text(
        "Line,Date,GTime\n" "1270,2025/12/16,65119.8\n" "1270,2025/12/16,65119.9\n",
        encoding="utf-8",
    )

    df = pd.DataFrame(
        [
            {
                "line_id": "1270.0",
                "record_id": "F02_1",
                "layer_no": 1,
                "_source_point_order": 1,
            },
            {
                "line_id": "1270.0",
                "record_id": "F02_1",
                "layer_no": 2,
                "_source_point_order": 1,
            },
            {
                "line_id": "1270.0",
                "record_id": "F02_2",
                "layer_no": 1,
                "_source_point_order": 2,
            },
        ]
    )

    enriched = aem_ingest_service._apply_acquisition_metadata_timestamps(
        df,
        [{"source_path": str(acquisition_path), "flight_id": "F02"}],
        flight_id="F02",
    )

    assert enriched["date_acquired"].tolist() == [
        "2025/12/16",
        "2025/12/16",
        "2025/12/16",
    ]


def test_run_ingest_ignores_non_flight_filename_suffix_for_timestamp_join(
    monkeypatch, tmp_path: Path
):
    source_path = tmp_path / "rho_GL250193_test.csv"
    source_path.write_text(
        "record,line_no,utmx,utmy,elevation,top_1_layer_m,bottom_1_layer_m,rho_1_layer_m\n"
        "1,1270,387229.86,3854803.25,2058.3,0,10,100\n",
        encoding="utf-8",
    )
    raw_path = tmp_path / "raw_GL250193_F14.csv"
    raw_path.write_text(
        "Line,Date,GTime\n" "1270,2025/12/16,65119.8\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(aem_ingest_service, "load_to_postgis", lambda df, config: 0)
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

    captured: dict[str, object] = {}

    def fake_build_stac_collection(
        df,
        config,
        parquet_gcs_path,
        raw_manifest_gcs_path,
        raw_file_paths=None,
        kind="inversion",
    ):
        if kind == "raw":
            captured["interval"] = aem_stac_service._stac_temporal_extent(df, config)
        return {
            "id": f"aem-gila_animas_2025-{kind}",
            "assets": {},
            "ocotillo:collection_kind": kind,
        }

    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "build_stac_collection",
        fake_build_stac_collection,
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "build_stac_items",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "write_stac_payloads",
        lambda *args, **kwargs: {
            "collection_gcs_path": "surveys/test/metadata/stac/collection.json",
            "items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "collection_gcs_paths": {
                "raw": "surveys/test/metadata/stac/raw_collection.json",
                "inversion": "surveys/test/metadata/stac/collection.json",
            },
        },
    )
    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "load_stac_to_pgstac",
        lambda *args, **kwargs: None,
    )

    class FakeStorageClient:
        def bucket(self, _name):
            raise AssertionError("bucket should not be used by patched writers")

    monkeypatch.setattr(
        "services.aem_ingest.storage.Client", lambda: FakeStorageClient()
    )

    config = IngestConfig(
        filepath=str(source_path),
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_test.csv",
    )

    aem_ingest_service.run_ingest(
        config,
        raw_file_paths=[],
        acquisition_file_paths=[{"source_path": str(raw_path), "flight_id": "F14"}],
    )

    assert captured["interval"] == ("2025-12-16T00:00:00Z", "2025-12-16T00:00:00Z")


def test_build_raw_stac_items_from_acquisition_csv_points(tmp_path: Path):
    acquisition_path = tmp_path / "raw_GL250193_F02.csv"
    acquisition_path.write_text(
        "Line,UTMX,UTMY,Date,GTime\n"
        "1270,500000,3800000,2025/12/16,65119.8\n"
        "1270,500100,3800100,2025/12/16,65120.9\n",
        encoding="utf-8",
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

    raw_df = aem_stac_service.build_raw_stac_dataframe(
        acquisition_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "source_path": str(acquisition_path),
                "flight_id": "F02",
            }
        ],
        raw_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "gcs_path": "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv",
                "flight_id": "F02",
            }
        ],
        source_epsg=26913,
    )
    raw_collection = aem_stac_service.build_stac_collection(
        df=raw_df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        raw_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "gcs_path": "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv",
                "flight_id": "F02",
            }
        ],
        kind="raw",
    )
    raw_items = aem_stac_service.build_raw_stac_items(
        raw_df,
        config=config,
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert len(raw_df) == 2
    assert raw_collection["extent"]["temporal"]["interval"] == [
        ["2025-12-16T18:05:19.800000Z", "2025-12-16T18:05:20.900000Z"]
    ]
    assert len(raw_items) == 2
    assert raw_items[0]["collection"] == "aem-gila_animas_2025-raw"
    assert raw_items[0]["properties"]["datetime"] == "2025-12-16T18:05:19.800000Z"
    assert raw_items[0]["assets"]["source"]["href"] == (
        "https://storage.googleapis.com/example-bucket/"
        "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv"
    )


def test_raw_collection_temporal_extent_ignores_blank_gtime_when_time_column_exists(
    caplog,
    tmp_path: Path,
):
    acquisition_path = tmp_path / "raw_GL250193_F02.csv"
    acquisition_path.write_text(
        "Line,UTMX,UTMY,Date,GTime\n"
        "1270,500000,3800000,2025/11/18,\n"
        "1270,500100,3800100,2025/11/18,65701.2\n"
        "1270,500200,3800200,2025/12/09,75658\n",
        encoding="utf-8",
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

    raw_df = aem_stac_service.build_raw_stac_dataframe(
        acquisition_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "source_path": str(acquisition_path),
                "flight_id": "F02",
            }
        ],
        raw_file_paths=[],
        source_epsg=26913,
    )
    raw_collection = aem_stac_service.build_stac_collection(
        df=raw_df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        kind="raw",
    )

    assert raw_collection["extent"]["temporal"]["interval"] == [
        ["2025-11-18T18:15:01.200000Z", "2025-12-09T21:00:58Z"]
    ]
    assert "raw_GL250193_F02.csv has 1 rows with unusable GTime values" in caplog.text
    assert "sample CSV rows: [2]" in caplog.text


def test_raw_stac_datetime_uses_seconds_of_day_for_gtime(
    caplog,
    tmp_path: Path,
):
    acquisition_path = tmp_path / "raw_GL250193_F02.csv"
    acquisition_path.write_text(
        "Line,x,y,Date,GTime\n"
        "L1270,706354.05414689,3617493.84057213,2025/11/24,66146.1\n",
        encoding="utf-8",
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

    raw_df = aem_stac_service.build_raw_stac_dataframe(
        acquisition_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "source_path": str(acquisition_path),
                "flight_id": "F02",
            }
        ],
        raw_file_paths=[],
        source_epsg=26912,
    )
    raw_items = aem_stac_service.build_raw_stac_items(
        raw_df,
        config=config,
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert raw_items[0]["properties"]["datetime"] == "2025-11-24T18:22:26.100000Z"
    assert "unusable GTime" not in caplog.text


def test_run_ingest_uploads_raw_point_items(monkeypatch, tmp_path: Path):
    source_path = tmp_path / "rho_GL250193_F02.csv"
    source_path.write_text("placeholder", encoding="utf-8")
    acquisition_path = tmp_path / "raw_GL250193_F02.csv"
    acquisition_path.write_text(
        "Line,UTMX,UTMY,Date,GTime\n"
        "1270,500000,3800000,2025/12/16,65119.8\n"
        "1270,500100,3800100,2025/12/16,65120.9\n",
        encoding="utf-8",
    )

    parsed_df = pd.DataFrame(
        [
            {
                "record_id": "F02_1",
                "line_id": "1270",
                "layer_no": 1,
                "easting": 500000,
                "northing": 3800000,
                "depth_top": 0,
                "depth_bot": 10,
                "resistivity": 100,
                "source_epsg": 26913,
            }
        ]
    )

    monkeypatch.setattr(
        aem_ingest_service, "detect_format", lambda _path: SourceFormat.SEOGI_RHO
    )
    monkeypatch.setattr(
        aem_ingest_service,
        "parse_seogi_rho",
        lambda _path, flight_id=None, source_epsg=32612: parsed_df.copy(),
    )
    monkeypatch.setattr(aem_ingest_service, "load_to_postgis", lambda df, config: 0)
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
        "load_stac_to_pgstac",
        lambda collections, items: None,
    )

    captured: dict[str, object] = {}

    def fake_write_stac_payloads(
        collections, items, config, gcs_client, ensure_prefix_readmes
    ):
        captured["item_count"] = len(items)
        captured["raw_item_count"] = len(
            [item for item in items if item["collection"] == "aem-gila_animas_2025-raw"]
        )
        return {
            "collection_gcs_path": "surveys/test/metadata/stac/inversion_collection.json",
            "items_gcs_path": "surveys/test/metadata/stac/items.ndjson",
            "collection_gcs_paths": {
                "raw": "surveys/test/metadata/stac/raw_collection.json",
                "inversion": "surveys/test/metadata/stac/inversion_collection.json",
            },
        }

    monkeypatch.setattr(
        aem_ingest_service.aem_stac,
        "write_stac_payloads",
        fake_write_stac_payloads,
    )

    class FakeStorageClient:
        pass

    monkeypatch.setattr(
        aem_ingest_service.storage, "Client", lambda: FakeStorageClient()
    )

    config = IngestConfig(
        filepath=str(source_path),
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/aem/inversion/preliminary/rho_GL250193_F02.csv",
    )

    result = aem_ingest_service.run_ingest(
        config,
        raw_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "gcs_path": "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv",
                "flight_id": "F02",
            }
        ],
        acquisition_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "source_path": str(acquisition_path),
                "flight_id": "F02",
            }
        ],
    )

    assert captured["item_count"] == 3
    assert captured["raw_item_count"] == 2
    assert result["stac_item_count"] == 3


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

    raw_collection = aem_stac_service.build_stac_collection(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        kind="raw",
    )
    inversion_collection = aem_stac_service.build_stac_collection(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        kind="inversion",
    )
    items = aem_stac_service.build_stac_items(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert raw_collection["id"] == "aem-gila_animas_2025-raw"
    assert "geometry" not in raw_collection
    assert raw_collection["extent"]["temporal"]["interval"] == [
        [
            "2025-03-01T00:00:00Z",
            "2025-03-02T00:00:00Z",
        ]
    ]
    assert (
        inversion_collection["assets"]["parquet"]["href"]
        == "https://storage.googleapis.com/example-bucket/"
        "surveys/gila_animas_2025/out.parquet"
    )
    assert inversion_collection["id"] == (
        "aem-gila_animas_2025-preliminary_inversion-seogi_python"
    )
    assert inversion_collection["extent"]["temporal"]["interval"] == [[None, None]]
    assert [item["id"] for item in items] == [
        "aem-gila_animas_2025-preliminary_inversion-L1-R1",
        "aem-gila_animas_2025-preliminary_inversion-L2-R2",
    ]
    assert items[0]["properties"]["datetime"] == "2025-03-01T00:00:00Z"
    assert items[1]["properties"]["datetime"] == "2025-03-02T00:00:00Z"
    assert "start_datetime" not in items[0]["properties"]
    assert "end_datetime" not in items[0]["properties"]
    assert "wms" not in raw_collection["assets"]
    assert "wfs" not in raw_collection["assets"]
    assert "wcs" not in raw_collection["assets"]
    assert items[0]["collection"] == inversion_collection["id"]


def test_build_stac_collection_includes_raw_data_assets():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 1),
            }
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
        raw_file_paths=[
            {
                "file": "raw_GL250193_F02.csv",
                "gcs_path": "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv",
                "flight_id": "F02",
            }
        ],
        kind="raw",
    )

    assert collection["assets"]["raw_raw_gl250193_f02"]["href"] == (
        "https://storage.googleapis.com/example-bucket/"
        "surveys/gila_animas_2025/acquisition/raw/raw_GL250193_F02.csv"
    )
    assert collection["assets"]["raw_raw_gl250193_f02"]["type"] == "text/csv"
    assert collection["assets"]["raw_raw_gl250193_f02"]["roles"] == ["data"]
    assert collection["assets"]["raw_raw_gl250193_f02"]["ocotillo:flight_id"] == "F02"


def test_build_stac_collection_geometry_uses_item_footprint_not_bbox_polygon():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 1),
            },
            {
                "line_id": "L2",
                "record_id": "R2",
                "easting": 500100,
                "northing": 3800100,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 2),
            },
            {
                "line_id": "L3",
                "record_id": "R3",
                "easting": 500200,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 3),
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
        kind="raw",
    )

    assert "geometry" not in collection


def test_build_stac_collection_uses_date_only_from_acquisition_datetime():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "acquisition_datetime": datetime.datetime(
                    2025, 3, 1, 14, 15, tzinfo=datetime.timezone.utc
                ),
            },
            {
                "line_id": "L2",
                "record_id": "R2",
                "easting": 500100,
                "northing": 3800100,
                "source_epsg": 32613,
                "acquisition_datetime": datetime.datetime(
                    2025, 3, 2, 9, 45, tzinfo=datetime.timezone.utc
                ),
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

    raw_collection = aem_stac_service.build_stac_collection(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        kind="raw",
    )
    inversion_collection = aem_stac_service.build_stac_collection(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
        kind="inversion",
    )
    items = aem_stac_service.build_stac_items(
        df=df,
        config=config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert raw_collection["extent"]["temporal"]["interval"] == [
        [
            "2025-03-01T00:00:00Z",
            "2025-03-02T00:00:00Z",
        ]
    ]
    assert inversion_collection["extent"]["temporal"]["interval"] == [[None, None]]
    assert items[0]["properties"]["datetime"] == "2025-03-01T00:00:00Z"
    assert "start_datetime" not in items[0]["properties"]
    assert "end_datetime" not in items[0]["properties"]


def test_finalize_parsed_dataframe_normalizes_raw_temporal_headers():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "layer_no": 1,
                "easting": 500000,
                "northing": 3800000,
                "resistivity": 100,
                "DATE": "2025-03-01",
                "TIME": "14:15:00",
            }
        ]
    )

    normalized = finalize_parsed_dataframe(df, "test-source", source_epsg=26913)

    assert normalized.loc[0, "date_acquired"] == "2025-03-01"
    assert normalized.loc[0, "acquisition_time"] == "14:15:00"


def test_build_stac_items_ignore_gtime_and_use_date_only():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "layer_no": 1,
                "easting": 500000,
                "northing": 3800000,
                "elevation": 1500,
                "depth_top": 0,
                "depth_bot": 10,
                "thickness": 10,
                "resistivity": 100,
                "Date": "2025-03-01",
                "GTime": "141500",
            }
        ]
    )

    normalized = finalize_parsed_dataframe(df, "test-source", source_epsg=26913)
    config = IngestConfig(
        filepath="/tmp/input.csv",
        survey_id="gila_animas_2025",
        processing_stage=ProcessingStage.PRELIMINARY,
        inversion_code=InversionCode.SEOGI_PYTHON,
        contractor="GeoTech/Seogi",
        gcs_bucket="example-bucket",
        source_gcs_path="surveys/gila_animas_2025/source.csv",
    )

    items = aem_stac_service.build_stac_items(
        normalized,
        config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert normalized.loc[0, "acquisition_time"] == "141500"
    assert items[0]["properties"]["datetime"] == "2025-03-01T00:00:00Z"


def test_build_stac_items_use_start_and_end_datetime_for_multiday_soundings():
    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "layer_no": 1,
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 1),
            },
            {
                "line_id": "L1",
                "record_id": "R1",
                "layer_no": 2,
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
                "date_acquired": datetime.date(2025, 3, 2),
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

    items = aem_stac_service.build_stac_items(
        df,
        config,
        parquet_gcs_path="surveys/gila_animas_2025/out.parquet",
        raw_manifest_gcs_path="surveys/gila_animas_2025/raw_files.json",
    )

    assert len(items) == 1
    assert "datetime" not in items[0]["properties"]
    assert items[0]["properties"]["start_datetime"] == "2025-03-01T00:00:00Z"
    assert items[0]["properties"]["end_datetime"] == "2025-03-02T00:00:00Z"


def test_limit_stac_items_per_collection_caps_each_collection():
    items = [{"id": f"raw-{i}", "collection": "raw"} for i in range(1002)] + [
        {"id": f"inversion-{i}", "collection": "inversion"} for i in range(1003)
    ]

    limited = aem_stac_service.limit_stac_items_per_collection(
        items,
        max_items_per_collection=1000,
    )

    assert len(limited) == 2000
    assert limited[0]["id"] == "raw-0"
    assert limited[999]["id"] == "raw-999"
    assert limited[1000]["id"] == "inversion-0"
    assert limited[-1]["id"] == "inversion-999"


def test_limit_stac_items_per_collection_uses_shared_remaining_budget():
    first_batch = [{"id": f"raw-{i}", "collection": "raw"} for i in range(1200)]
    second_batch = [{"id": f"raw-next-{i}", "collection": "raw"} for i in range(10)]
    remaining: dict[str, int] = {}

    first_limited = aem_stac_service.limit_stac_items_per_collection(
        first_batch,
        max_items_per_collection=1000,
        remaining_by_collection=remaining,
    )
    second_limited = aem_stac_service.limit_stac_items_per_collection(
        second_batch,
        max_items_per_collection=1000,
        remaining_by_collection=remaining,
    )

    assert len(first_limited) == 1000
    assert second_limited == []
    assert remaining == {"raw": 0}


def test_build_stac_collection_includes_survey_level_geoserver_assets(monkeypatch):
    monkeypatch.setenv("GEOSERVER_PUBLIC_URL", "https://maps.example.com")
    monkeypatch.setenv("GEOSERVER_WORKSPACE", "aem")

    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
            }
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
        kind="inversion",
    )

    assert collection["assets"]["wms"]["href"] == (
        "https://maps.example.com/geoserver/ows"
        "?service=WMS&version=1.3.0&request=GetCapabilities"
    )
    assert collection["assets"]["wfs"]["href"] == (
        "https://maps.example.com/geoserver/ows"
        "?service=WFS&version=2.0.0&request=GetFeature"
        "&typeNames=aem%3Aaem-gila_animas_2025-preliminary_inversion-seogi_python"
        "&outputFormat=application%2Fjson"
    )
    assert collection["assets"]["wcs"]["href"] == (
        "https://maps.example.com/geoserver/ows"
        "?service=WCS&version=2.0.1&request=DescribeCoverage"
        "&coverageId=aem%3Aaem-gila_animas_2025-preliminary_inversion-seogi_python"
    )
    assert collection["assets"]["wms"]["geoserver:layer"] == (
        "aem:aem-gila_animas_2025-preliminary_inversion-seogi_python"
    )


def test_build_stac_collection_deduplicates_geoserver_base_path(monkeypatch):
    monkeypatch.setenv("GEOSERVER_PUBLIC_URL", "https://maps.example.com/geoserver")
    monkeypatch.setenv("GEOSERVER_WORKSPACE", "aem")

    df = pd.DataFrame(
        [
            {
                "line_id": "L1",
                "record_id": "R1",
                "easting": 500000,
                "northing": 3800000,
                "source_epsg": 32613,
            }
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
        kind="inversion",
    )

    assert collection["assets"]["wcs"]["href"] == (
        "https://maps.example.com/geoserver/ows"
        "?service=WCS&version=2.0.1&request=DescribeCoverage"
        "&coverageId=aem%3Aaem-gila_animas_2025-preliminary_inversion-seogi_python"
    )


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

    collections = [
        {"id": "aem-gila_animas_2025-raw"},
        {"id": "aem-gila_animas_2025-inversion"},
    ]
    items = [{"id": "item-1", "collection": "aem-gila_animas_2025-inversion"}]

    aem_stac_service.load_stac_to_pgstac(collections, items)

    assert calls == [
        ("collections", collections, "upsert"),
        ("items", items, "upsert", 1000),
        ("disconnect", "postgresql://example"),
    ]


def test_load_stac_to_pgstac_skips_uninitialized_target(monkeypatch):
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
            raise Exception("Failed to detect the target database version.")

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

    collections = [
        {"id": "aem-gila_animas_2025-raw"},
        {"id": "aem-gila_animas_2025-inversion"},
    ]
    items = [{"id": "item-1", "collection": "aem-gila_animas_2025-inversion"}]

    aem_stac_service.load_stac_to_pgstac(collections, items)

    assert calls == [
        ("collections", collections, "upsert"),
        ("disconnect", "postgresql://example"),
    ]


def test_load_stac_to_pgstac_raises_unexpected_loader_errors(monkeypatch):
    class FakeMethods:
        upsert = "upsert"

    class FakeDB:
        def __init__(self, dsn):
            self.dsn = dsn

        def disconnect(self):
            return None

    class FakeLoader:
        def __init__(self, db):
            self.db = db

        def load_collections(self, file, insert_mode):
            raise Exception("permission denied for table collections")

        def load_items(self, file, insert_mode, chunksize):
            return None

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

    collections = [
        {"id": "aem-gila_animas_2025-raw"},
        {"id": "aem-gila_animas_2025-inversion"},
    ]
    items = [{"id": "item-1", "collection": "aem-gila_animas_2025-inversion"}]

    try:
        aem_stac_service.load_stac_to_pgstac(collections, items)
    except Exception as exc:
        assert str(exc) == "permission denied for table collections"
    else:
        raise AssertionError(
            "Expected load_stac_to_pgstac to re-raise the loader error"
        )


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
