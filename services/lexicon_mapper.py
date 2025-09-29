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
from transfers.util import read_csv


class LexiconMapper:
    def __init__(self):
        self._mappers = None

    def map_value(self, value):
        return self._make_lu_to_lexicon_mapper().get(value, value)

    def _make_lu_to_lexicon_mapper(self):
        if self._mappers:
            return self._mappers

        lu_tables = [
            # "LU_AltitudeDatum",     # the code is the value, so no need for mapping
            "LU_AltitudeMethod",  # CODE/MEANING
            "LU_CollectionMethod",  # CODE/MEANING
            "LU_ConstructionMethod",  # CODE/MEANING
            "LU_CoordinateAccuracy",  # CODE/MEANING
            # "LU_CoordinateDatum",   # the code is the value, so no need for mapping
            "LU_CoordinateMethod",  # CODE/MEANING
            "LU_CurrentUse",  # CODE/MEANING
            "LU_DataQuality",  # CODE/MEANING
            "LU_DataSource",  # CODE/MEANING
            "LU_Depth_CompletionSource",  # CODE/MEANING
            "LU_Discharge_ChemistrySource",  # CODE/MEANING
            # "LU_FieldNoteTypes",    # not being used in the transfers since there are no records
            # "LU_Formations",        # needs to be cleaned before it can be used
            "LU_LevelStatus",  # CODE/MEANING
            # "LU_Lithology",         # needs to be cleaned before it can be used
            "LU_MajorAnalyte",  # CODE/MEANING
            "LU_MeasurementMethod",  # CODE/MEANING
            # "LU_MeasuringAgency",   # the abreviation is what is used in the new schema
            "LU_MinorTraceAnalyte",  # CODE/MEANING
            "LU_MonitoringStatus",  # CODE/MEANING
            "LU_SampleType",  # CODE/MEANING
            "LU_SiteType",  # CODE/MEANING
            "LU_Status",  # CODE/MEANING
        ]

        mappers = {}

        for lu_table in lu_tables:
            table = read_csv(lu_table)

            for i, row in table.iterrows():
                if lu_table == "LU_Formations":
                    code = row.Code
                    meaning = row.Meaning
                else:
                    code = row.CODE
                    meaning = row.MEANING

                mappers.update({f"{lu_table}:{code}": meaning})
        self._mappers = mappers
        return mappers


lexicon_mapper = LexiconMapper()

# ============= EOF =============================================
