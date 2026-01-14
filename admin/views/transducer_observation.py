# ===============================================================================
# Copyright 2026
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
"""
TransducerObservationAdmin view for transducer observations.
"""
from admin.views.base import OcotilloModelView


class TransducerObservationAdmin(OcotilloModelView):
    """
    Admin view for TransducerObservation model.
    """

    # ========== Basic Configuration ==========

    name = "Transducer Observations"
    label = "Transducer Observations"
    icon = "fa fa-tachometer-alt"

    # ========== List View ==========

    sortable_fields = [
        "id",
        "observation_datetime",
        "value",
        "parameter_id",
        "deployment_id",
        "release_status",
    ]

    fields_default_sort = [("observation_datetime", True)]

    searchable_fields = [
        "observation_datetime",
        "parameter_id",
        "deployment_id",
        "release_status",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "observation_datetime",
        "value",
        "parameter_id",
        "deployment_id",
        "release_status",
        "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
        "nma_waterlevelscontinuous_pressure_checked_by",
        "nma_waterlevelscontinuous_pressure_created",
        "nma_waterlevelscontinuous_pressure_data_source",
        "nma_waterlevelscontinuous_pressure_global_id",
        "nma_waterlevelscontinuous_pressure_measurement_method",
        "nma_waterlevelscontinuous_pressure_measuring_agency",
        "nma_waterlevelscontinuous_pressure_notes",
        "nma_waterlevelscontinuous_pressure_processed_by",
        "nma_waterlevelscontinuous_pressure_qced",
        "nma_waterlevelscontinuous_pressure_temperature_water",
        "nma_waterlevelscontinuous_pressure_updated",
        "nma_waterlevelscontinuous_pressure_water_head",
        "nma_waterlevelscontinuous_pressure_water_head_adjusted",
        "nma_waterlevelscontinuous_acoustic_created",
        "nma_waterlevelscontinuous_acoustic_data_source",
        "nma_waterlevelscontinuous_acoustic_global_id",
        "nma_waterlevelscontinuous_acoustic_measurement_method",
        "nma_waterlevelscontinuous_acoustic_measuring_agency",
        "nma_waterlevelscontinuous_acoustic_notes",
        "nma_waterlevelscontinuous_acoustic_point_id",
        "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
        "nma_waterlevelscontinuous_acoustic_public_release",
        "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
        "nma_waterlevelscontinuous_acoustic_serial_no",
        "nma_waterlevelscontinuous_acoustic_server_receipt_date",
        "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
        "nma_waterlevelscontinuous_acoustic_temperature_air",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
        "nma_waterlevelscontinuous_pressure_checked_by",
        "nma_waterlevelscontinuous_pressure_created",
        "nma_waterlevelscontinuous_pressure_data_source",
        "nma_waterlevelscontinuous_pressure_global_id",
        "nma_waterlevelscontinuous_pressure_measurement_method",
        "nma_waterlevelscontinuous_pressure_measuring_agency",
        "nma_waterlevelscontinuous_pressure_notes",
        "nma_waterlevelscontinuous_pressure_processed_by",
        "nma_waterlevelscontinuous_pressure_qced",
        "nma_waterlevelscontinuous_pressure_temperature_water",
        "nma_waterlevelscontinuous_pressure_updated",
        "nma_waterlevelscontinuous_pressure_water_head",
        "nma_waterlevelscontinuous_pressure_water_head_adjusted",
        "nma_waterlevelscontinuous_acoustic_created",
        "nma_waterlevelscontinuous_acoustic_data_source",
        "nma_waterlevelscontinuous_acoustic_global_id",
        "nma_waterlevelscontinuous_acoustic_measurement_method",
        "nma_waterlevelscontinuous_acoustic_measuring_agency",
        "nma_waterlevelscontinuous_acoustic_notes",
        "nma_waterlevelscontinuous_acoustic_point_id",
        "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
        "nma_waterlevelscontinuous_acoustic_public_release",
        "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
        "nma_waterlevelscontinuous_acoustic_serial_no",
        "nma_waterlevelscontinuous_acoustic_server_receipt_date",
        "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
        "nma_waterlevelscontinuous_acoustic_temperature_air",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
        "nma_waterlevelscontinuous_pressure_checked_by",
        "nma_waterlevelscontinuous_pressure_created",
        "nma_waterlevelscontinuous_pressure_data_source",
        "nma_waterlevelscontinuous_pressure_global_id",
        "nma_waterlevelscontinuous_pressure_measurement_method",
        "nma_waterlevelscontinuous_pressure_measuring_agency",
        "nma_waterlevelscontinuous_pressure_notes",
        "nma_waterlevelscontinuous_pressure_processed_by",
        "nma_waterlevelscontinuous_pressure_qced",
        "nma_waterlevelscontinuous_pressure_temperature_water",
        "nma_waterlevelscontinuous_pressure_updated",
        "nma_waterlevelscontinuous_pressure_water_head",
        "nma_waterlevelscontinuous_pressure_water_head_adjusted",
        "nma_waterlevelscontinuous_acoustic_created",
        "nma_waterlevelscontinuous_acoustic_data_source",
        "nma_waterlevelscontinuous_acoustic_global_id",
        "nma_waterlevelscontinuous_acoustic_measurement_method",
        "nma_waterlevelscontinuous_acoustic_measuring_agency",
        "nma_waterlevelscontinuous_acoustic_notes",
        "nma_waterlevelscontinuous_acoustic_point_id",
        "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
        "nma_waterlevelscontinuous_acoustic_public_release",
        "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
        "nma_waterlevelscontinuous_acoustic_serial_no",
        "nma_waterlevelscontinuous_acoustic_server_receipt_date",
        "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
        "nma_waterlevelscontinuous_acoustic_temperature_air",
    ]

    readonly_fields = [
        "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
        "nma_waterlevelscontinuous_pressure_checked_by",
        "nma_waterlevelscontinuous_pressure_created",
        "nma_waterlevelscontinuous_pressure_data_source",
        "nma_waterlevelscontinuous_pressure_global_id",
        "nma_waterlevelscontinuous_pressure_measurement_method",
        "nma_waterlevelscontinuous_pressure_measuring_agency",
        "nma_waterlevelscontinuous_pressure_notes",
        "nma_waterlevelscontinuous_pressure_processed_by",
        "nma_waterlevelscontinuous_pressure_qced",
        "nma_waterlevelscontinuous_pressure_temperature_water",
        "nma_waterlevelscontinuous_pressure_updated",
        "nma_waterlevelscontinuous_pressure_water_head",
        "nma_waterlevelscontinuous_pressure_water_head_adjusted",
        "nma_waterlevelscontinuous_acoustic_created",
        "nma_waterlevelscontinuous_acoustic_data_source",
        "nma_waterlevelscontinuous_acoustic_global_id",
        "nma_waterlevelscontinuous_acoustic_measurement_method",
        "nma_waterlevelscontinuous_acoustic_measuring_agency",
        "nma_waterlevelscontinuous_acoustic_notes",
        "nma_waterlevelscontinuous_acoustic_point_id",
        "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
        "nma_waterlevelscontinuous_acoustic_public_release",
        "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
        "nma_waterlevelscontinuous_acoustic_serial_no",
        "nma_waterlevelscontinuous_acoustic_server_receipt_date",
        "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
        "nma_waterlevelscontinuous_acoustic_temperature_air",
    ]


# ============= EOF =============================================
