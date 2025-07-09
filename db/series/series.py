# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from sqlalchemy import DateTime, Float, String, Integer, ForeignKey, Text, func
from sqlalchemy.orm import declared_attr, mapped_column, relationship

from db.base import AutoBaseMixin, Base, ReleaseMixin, lexicon_term


class QCMixin:
    @declared_attr
    def quality_control_status(self):
        return lexicon_term(default="Provisional")

    @declared_attr
    def quality_control_notes(self):
        return mapped_column(Text)

    @declared_attr
    def quality_control_timestamp(self):
        return mapped_column(DateTime, nullable=True, server_onupdate=func.now())

    @declared_attr
    def quality_control_user_id(self):
        return mapped_column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
        )


class SeriesMixin:
    @declared_attr
    def series_id(self):
        return mapped_column(
            Integer,
            ForeignKey("series.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )


class Series(Base, AutoBaseMixin, ReleaseMixin):
    """
    Base class for series that can be associated with samples.
    This class can be extended to create specific series types.
    """

    # observed_property = mapped_column(
    #     String(100),
    #     ForeignKey("lexicon_term.term", ondelete="CASCADE"),
    #     nullable=False,
    # )

    observed_property = lexicon_term(nullable=False)
    unit = lexicon_term(nullable=False)

    name = mapped_column(String(255), nullable=False)
    description = mapped_column(Text, nullable=True)

    sensor_id = mapped_column(
        Integer,
        ForeignKey("sensor.id", ondelete="CASCADE"),
        nullable=True,
    )

    thing_id = mapped_column(
        Integer,
        ForeignKey("thing.id", ondelete="CASCADE"),
        nullable=False,
    )


# class SampleWellAssociation(Base, AutoBaseMixin):
#     sample_id = mapped_column(
#         "sample_id",
#         Integer,
#         ForeignKey("sample.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#     well_id = mapped_column(
#         "well_id",
#         Integer,
#         ForeignKey("well.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#
#     sample = relationship("Sample", back_populates="well_associations")
#
#
# class TimeSeries(Base, AutoBaseMixin):
#     observed_property = mapped_column(
#         String(100),
#         ForeignKey("lexicon_term.term", ondelete="CASCADE"),
#         nullable=False,
#     )
#     unit = mapped_column(String(100), ForeignKey("lexicon_term.term"), nullable=False)
#
#
# class TimeObservation(Base, AutoBaseMixin, QCMixin):
#     timestamp = mapped_column(DateTime, nullable=False)
#     value = mapped_column(Float, nullable=False)
#
#     sample_id = mapped_column(
#         "sample_id",
#         Integer,
#         ForeignKey("sample.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#     time_series_id = mapped_column(
#         "time_series_id",
#         Integer,
#         ForeignKey("time_series.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#
#
# class DomainSeries(Base, AutoBaseMixin):
#     domain = mapped_column(String(100), ForeignKey("lexicon_term.term"), nullable=False)
#     observed_property = mapped_column(
#         String(100), ForeignKey("lexicon_term.term"), nullable=False
#     )
#     domain_unit = mapped_column(
#         String(100), ForeignKey("lexicon_term.term"), nullable=False
#     )
#     value_unit = mapped_column(
#         String(100), ForeignKey("lexicon_term.term"), nullable=False
#     )
#
#
# class DomainObservation(Base, AutoBaseMixin):
#     value = mapped_column(Float, nullable=False)
#     domain_value = mapped_column(Float, nullable=False)
#     timestamp = mapped_column(DateTime, nullable=True)
#
#     sample_id = mapped_column(
#         "sample_id",
#         Integer,
#         ForeignKey("sample.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#
#     domain_series_id = mapped_column(
#         "domain_series_id",
#         Integer,
#         ForeignKey("domain_series.id", ondelete="CASCADE"),
#         nullable=False,
#     )

# sample_domain_series = relationship(
#     "SampleDomainSeries", back_populates="observations", cascade="all, delete-orphan"
# )


# class WellTimeseries(Base, TimeseriesMixin, AutoBaseMixin, PropertiesMixin):
#     well_id = mapped_column(
#         "well_id", Integer, ForeignKey("well.id", ondelete="CASCADE"), nullable=False
#     )
#
#     equipment_id = mapped_column(
#         "equipment_id",
#         Integer,
#         ForeignKey("equipment.id", ondelete="SET NULL"),
#         nullable=True,
#     )
#
#
# class GroundwaterLevelObservation(Base, AutoBaseMixin, PropertiesMixin, QCMixin):
#     """ """
#
#     # __table_args__ = {"timescaledb_hypertable": {"time_column_name": "timestamp"}}
#
#     # Define common fields for observations here
#     timestamp = mapped_column(DateTime, nullable=False)
#     value = mapped_column(Float, nullable=False)
#     unit = mapped_column(String, nullable=False, default="ftbgs")
#
#     data_quality = mapped_column(String(100), ForeignKey("lexicon_term.term"))
#     level_status = mapped_column(String(100), ForeignKey("lexicon_term.term"))
#
#     timeseries_id = mapped_column(
#         "timeseries_id",
#         Integer,
#         ForeignKey("well_timeseries.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#
#     timeseries = relationship("WellTimeseries", backref="observations")
#
#     def __repr__(self):
#         return f"<Observation(id={self.id}, timestamp={self.timestamp}, value={self.value})>"


# ============= EOF =============================================
