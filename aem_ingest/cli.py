"""
aem_ingest.cli — Typer CLI for the AEM ingest pipeline.

Usage:
  aem-ingest run rho_GL250193_F02.csv \\
    --survey-id gila_animas_2025 \\
    --stage preliminary_inversion \\
    --inversion-code seogi_python \\
    --contractor "GeoTech/Seogi" \\
    --db-conn "postgresql://user:pass@host/db" \\
    --gcs-bucket nmbgmr-aem

  aem-ingest detect rho_GL250193_F02.csv

  aem-ingest parse rho_GL250193_F02.csv --flight-id F02 --out parsed.parquet
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

app = typer.Typer(
    name="aem-ingest",
    help="NMBGMR AEM ingest pipeline — load inversion files to PostGIS + GCS",
    no_args_is_help=True,
)


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI use."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# aem-ingest run — full pipeline
# ---------------------------------------------------------------------------


@app.command()
def run(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    survey_id: Annotated[
        str, typer.Option("--survey-id", help="e.g. gila_animas_2025")
    ],
    stage: Annotated[
        str,
        typer.Option(
            "--stage",
            help="Processing stage",
            click_type=click.Choice(["preliminary_inversion", "final_inversion"]),
        ),
    ],
    inversion_code: Annotated[
        str,
        typer.Option(
            "--inversion-code",
            help="Inversion software",
            click_type=click.Choice(["seogi_python", "aarhus_sci", "aarhus_lci"]),
        ),
    ],
    contractor: Annotated[
        str, typer.Option("--contractor", help="e.g. 'GeoTech/Seogi'")
    ],
    db_conn: Annotated[
        str, typer.Option("--db-conn", help="PostgreSQL connection string")
    ],
    gcs_bucket: Annotated[
        str, typer.Option("--gcs-bucket", help="GCS bucket name")
    ],
    source_gcs_path: Annotated[
        str,
        typer.Option(
            "--source-gcs-path",
            help=(
                "GCS path for the source file (from the mapper's proposed_gcs_path). "
                "e.g. 'surveys/estancia_2025/aem/inversion/preliminary/rho_GL250194_F01.csv'"
            ),
        ),
    ],
    flight_id: Annotated[
        Optional[str],
        typer.Option("--flight-id", help="Flight ID for Seogi (e.g. F02)"),
    ] = None,
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            help="SkyTEM system for AGF",
            click_type=click.Choice(["306hp", "312hp"]),
        ),
    ] = None,
    date_acquired: Annotated[
        Optional[str],
        typer.Option("--date-acquired", help="Acquisition date (YYYY-MM-DD)"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Run the full ingest pipeline for a single AEM inversion file."""
    _setup_logging(verbose)

    from aem_ingest.schemas import (
        IngestConfig,
        InversionCode,
        ProcessingStage,
        SkytemSystem,
    )
    from aem_ingest.pipeline import run_ingest

    # Build validated config from CLI args
    config = IngestConfig(
        filepath=str(filepath),
        survey_id=survey_id,
        processing_stage=ProcessingStage(stage),
        inversion_code=InversionCode(inversion_code),
        contractor=contractor,
        db_conn_string=db_conn,
        gcs_bucket=gcs_bucket,
        source_gcs_path=source_gcs_path,
        flight_id=flight_id,
        system=SkytemSystem(system) if system else None,
        date_acquired=(
            datetime.date.fromisoformat(date_acquired) if date_acquired else None
        ),
    )

    stac_stub = run_ingest(config)
    typer.echo(json.dumps(stac_stub, indent=2))


# ---------------------------------------------------------------------------
# aem-ingest detect — format detection only
# ---------------------------------------------------------------------------


@app.command()
def detect(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Detect the format of an AEM inversion file (no DB or GCS needed)."""
    _setup_logging(verbose)

    from aem_ingest.parsers import detect_format

    fmt = detect_format(str(filepath))
    typer.echo(f"Format: {fmt.value}")


# ---------------------------------------------------------------------------
# aem-ingest parse — parse only, no DB/GCS
# ---------------------------------------------------------------------------


@app.command()
def parse(
    filepath: Annotated[
        Path, typer.Argument(help="Path to the inversion file", exists=True)
    ],
    flight_id: Annotated[
        Optional[str],
        typer.Option("--flight-id", help="Flight ID for Seogi (e.g. F02)"),
    ] = None,
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            help="SkyTEM system for AGF",
            click_type=click.Choice(["306hp", "312hp"]),
        ),
    ] = None,
    out: Annotated[
        Optional[Path],
        typer.Option("--out", "-o", help="Output path (.parquet or .csv)"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Debug logging")
    ] = False,
):
    """Parse an AEM file to canonical schema without loading to DB.

    Useful for local inspection, notebook use, and testing.
    Outputs to stdout (CSV) or to a file (.parquet or .csv).
    """
    _setup_logging(verbose)

    from aem_ingest.parsers import detect_format, parse_agf_lci, parse_bylayer, parse_seogi_rho
    from aem_ingest.schemas import SourceFormat

    fmt = detect_format(str(filepath))

    if fmt == SourceFormat.BYLAYER:
        df = parse_bylayer(str(filepath))
    elif fmt == SourceFormat.SEOGI_RHO:
        df = parse_seogi_rho(str(filepath), flight_id=flight_id)
    elif fmt == SourceFormat.AGF_LCI:
        if system is None:
            typer.echo("Error: AGF LCI format requires --system (306hp or 312hp)", err=True)
            raise typer.Exit(code=1)
        df = parse_agf_lci(str(filepath), system=system)

    typer.echo(
        f"Parsed: {len(df):,} rows, {df['record_id'].nunique():,} soundings",
        err=True,
    )

    if out is None:
        # Print summary to stdout
        typer.echo(df.describe().to_string())
    elif str(out).endswith(".parquet"):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from aem_ingest.parsers.common import CANONICAL_COLUMNS

        cols = [c for c in CANONICAL_COLUMNS if c in df.columns]
        table = pa.Table.from_pandas(df[cols], preserve_index=False)
        pq.write_table(table, str(out), compression="snappy")
        typer.echo(f"Written to {out}", err=True)
    else:
        df.to_csv(str(out), index=False)
        typer.echo(f"Written to {out}", err=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
