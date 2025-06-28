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
from sqlalchemy import Integer, ForeignKey, Float, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.testing.schema import mapped_column

from db import AutoBaseMixin, Base


class WaterChemistryAnalysis(Base, AutoBaseMixin):
    """
    Represents a chemical analysis of a well.
    """

    __tablename__ = "water_chemistry_analysis"

    analysis_set_id = mapped_column(
        Integer, ForeignKey("water_chemistry_analysis_set.id")
    )
    value = mapped_column(Float)
    unit = mapped_column(String(100), ForeignKey("lexicon_term.term"), nullable=True)
    uncertainty = mapped_column(Float, nullable=True)
    method = mapped_column(String(100), nullable=True)
    analyte = mapped_column(
        String(100), ForeignKey("lexicon_term.term"), nullable=False
    )
    analysis_timestamp = mapped_column(
        DateTime
    )  # Timestamp of when the analysis was performed

    # Add relationships if necessary


class WaterChemistryAnalysisSet(Base, AutoBaseMixin):
    """
    Represents a set of chemical analyses for a well.
    This can be used to group multiple analyses together.
    """

    __tablename__ = "water_chemistry_analysis_set"

    well_id = mapped_column(Integer, ForeignKey("well.id" , ondelete='CASCADE'))
    note = mapped_column(String(255), nullable=True)

    collection_timestamp = mapped_column(DateTime, nullable=False)

    laboratory = mapped_column(
        String(255), nullable=True
    )  # Name of the laboratory that performed the analysis

    collection_method = mapped_column(
        String(100),
        ForeignKey("lexicon_term.term"),
        nullable=True,
    )  # Method used for sample collection

    sample_type = mapped_column(
        String(100),
        ForeignKey("lexicon_term.term"),
        nullable=True,
    )  # Type of sample collected (e.g., groundwater, surface water)

    visible = mapped_column(
        Boolean, default=False, nullable=False
    )  # Visibility of the analysis set (1 for visible, 0 for hidden)
    # Define relationships
    analyses = relationship("WaterChemistryAnalysis", backref="analysis_set")
    well = relationship("Well", backref="analysis_sets")


# ============= EOF =============================================
