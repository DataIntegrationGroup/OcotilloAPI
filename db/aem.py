# flake8: noqa: E501
"""
db.aem — SQLAlchemy ORM models for the AEM PostGIS schema.

These models define the aem_soundings and aem_sounding_metadata tables.
Alembic uses these models as the source of truth for migrations:
  alembic revision --autogenerate -m "add aem tables"

The models mirror the DDL in the session summary doc, with two additions:
  - SQLAlchemy column types map to the PostGIS types
  - GeoAlchemy2 handles the GEOMETRY(Point, 26913) columns

Design notes for non-SQLAlchemy readers:
  - sounding_id is auto-generated (BIGSERIAL) — never set it manually
  - loaded_at defaults to NOW() — the database stamps it on insert
  - record_id is TEXT, not INTEGER, because Seogi's record column
    resets to 1 per flight subfolder and must be prefixed with flight ID
    (e.g. F02_1) to be unique across a survey
"""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

# ---------------------------------------------------------------------------
# aem_soundings — one row per layer per sounding
# ---------------------------------------------------------------------------


class AemSounding(Base):
    """A single resistivity layer within a single AEM sounding.

    This is the main data table.  Each row represents one layer at one
    sounding location, with resistivity (and optionally uncertainty,
    conductivity, DOI).

    The table is large — Mimbres alone is ~5.5M rows (140k soundings × 39
    layers).  Indexes on geom, survey_id+processing_stage, depth range,
    and line_id support the common query patterns.
    """

    __tablename__ = "aem_soundings"

    # Primary key — auto-generated, never set by ingest code
    sounding_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )

    # ---- Provenance ----
    survey_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    processing_stage: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="'preliminary_inversion' or 'final_inversion'",
    )
    inversion_code: Mapped[str | None] = mapped_column(
        Text,
        comment="'seogi_python' | 'aarhus_sci' | 'aarhus_lci'",
    )
    contractor: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(
        Text, comment="GCS path of the original source file"
    )
    source_epsg: Mapped[int | None] = mapped_column(
        Integer, comment="Original CRS before reprojection (e.g. 32613 for Seogi)"
    )

    # ---- Identifiers ----
    line_id: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[str | None] = mapped_column(
        Text,
        comment=(
            "TEXT not INTEGER — Seogi record resets to 1 per flight subfolder. "
            "Prefixed with flight ID (e.g. F02_1) to be unique across survey."
        ),
    )
    layer_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # ---- Position (all stored in EPSG:26913 after reprojection) ----
    geom = Column(
        Geometry(geometry_type="POINT", srid=26913),
        nullable=False,
        comment="PostGIS point in NAD83 UTM Zone 13N",
    )
    easting_m: Mapped[float] = mapped_column(Float, nullable=False)
    northing_m: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_dd: Mapped[float | None] = mapped_column(Float)
    latitude_dd: Mapped[float | None] = mapped_column(Float)

    # ---- Elevation ----
    elevation_m: Mapped[float | None] = mapped_column(Float)
    sensor_alt_m: Mapped[float | None] = mapped_column(Float)
    terrain_clear_m: Mapped[float | None] = mapped_column(Float)

    # ---- Layer geometry (depths are negative = below surface) ----
    depth_top_m: Mapped[float] = mapped_column(Float, nullable=False)
    depth_bot_m: Mapped[float] = mapped_column(Float, nullable=False)
    thickness_m: Mapped[float | None] = mapped_column(
        Float, comment="NULL for Seogi outputs"
    )

    # ---- Inversion result ----
    resistivity_ohmm: Mapped[float] = mapped_column(Float, nullable=False)

    # ---- Uncertainty (NULL when pipeline doesn't produce it) ----
    # NULL is meaningful here: it means the inversion pipeline didn't
    # estimate uncertainty, not that the value is unknown.  Seogi's Python
    # pipeline produces no uncertainty.  Aarhus Workbench and AGF LCI do.
    resistivity_std: Mapped[float | None] = mapped_column(
        Float, comment="NULL for Seogi — pipeline doesn't produce uncertainty"
    )
    conductivity_sm: Mapped[float | None] = mapped_column(
        Float, comment="NULL for Seogi"
    )
    doi_conservative_m: Mapped[float | None] = mapped_column(
        Float, comment="NULL for Seogi"
    )
    doi_standard_m: Mapped[float | None] = mapped_column(
        Float, comment="NULL for Seogi"
    )
    resdata: Mapped[float | None] = mapped_column(Float)
    restotal: Mapped[float | None] = mapped_column(Float)
    plni: Mapped[float | None] = mapped_column(Float)

    # ---- Timestamps ----
    date_acquired: Mapped[date | None] = mapped_column(Date)
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- Indexes ----
    __table_args__ = (
        Index("idx_soundings_geom", geom, postgresql_using="gist"),
        Index("idx_soundings_survey_stage", "survey_id", "processing_stage"),
        Index("idx_soundings_depth", "depth_top_m", "depth_bot_m"),
        Index("idx_soundings_line", "survey_id", "line_id"),
        Index(
            "idx_soundings_final",
            "survey_id",
            "line_id",
            postgresql_where=text("processing_stage = 'final_inversion'"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AemSounding survey={self.survey_id} "
            f"line={self.line_id} record={self.record_id} "
            f"layer={self.layer_no}>"
        )


# ---------------------------------------------------------------------------
# aem_sounding_metadata — one row per sounding (aggregated)
# ---------------------------------------------------------------------------


class AemSoundingMetadata(Base):
    """Summary row for a single AEM sounding (aggregated across layers).

    One row per unique (survey_id, line_id, record_id, processing_stage).
    Populated by the ingest pipeline after loading layer-level data.
    Used for fast sounding-level spatial queries and map display
    without joining the much larger aem_soundings table.
    """

    __tablename__ = "aem_sounding_metadata"

    # ---- Composite primary key ----
    survey_id: Mapped[str] = mapped_column(Text, primary_key=True)
    line_id: Mapped[str] = mapped_column(Text, primary_key=True)
    record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    processing_stage: Mapped[str] = mapped_column(Text, primary_key=True)

    # ---- Position ----
    geom = Column(
        Geometry(geometry_type="POINT", srid=26913),
        nullable=False,
    )
    easting_m: Mapped[float] = mapped_column(Float, nullable=False)
    northing_m: Mapped[float] = mapped_column(Float, nullable=False)

    # ---- Flight / time ----
    flight_id: Mapped[str | None] = mapped_column(Text)
    date_acquired: Mapped[date | None] = mapped_column(Date)

    # ---- Aggregated stats ----
    num_layers: Mapped[int | None] = mapped_column(SmallInteger)
    max_depth_m: Mapped[float | None] = mapped_column(Float)
    has_uncertainty: Mapped[bool] = mapped_column(Boolean, default=False)
    has_doi: Mapped[bool] = mapped_column(Boolean, default=False)

    # ---- Provenance ----
    inversion_code: Mapped[str | None] = mapped_column(Text)
    source_epsg: Mapped[int | None] = mapped_column(Integer)

    # ---- Indexes ----
    __table_args__ = (
        Index("idx_metadata_geom", geom, postgresql_using="gist"),
        Index("idx_metadata_survey", "survey_id", "processing_stage"),
    )

    def __repr__(self) -> str:
        return (
            f"<AemSoundingMetadata survey={self.survey_id} "
            f"line={self.line_id} record={self.record_id}>"
        )
