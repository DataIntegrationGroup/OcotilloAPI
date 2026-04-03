# ===============================================================================
# Copyright 2026 ross
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
BDD step definitions for chemistry backfill features.

These steps are designed to be reusable across all chemistry types
(Radionuclides, MajorChemistry, MinorTraceChemistry, FieldParameters).
"""

import uuid
from datetime import datetime, timezone

from behave import given, when, then
from behave.runner import Context
from sqlalchemy import select

from db import Location, Thing, LocationThingAssociation
from db.analysis_method import AnalysisMethod
from db.engine import session_ctx
from db.field import FieldEvent, FieldActivity
from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_MinorTraceChemistry,
    NMA_Radionuclides,
)
from db.notes import Notes
from db.observation import Observation
from db.parameter import Parameter
from db.sample import Sample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_backfill_tracking(context: Context):
    """Initialize per-scenario tracking lists for cleanup."""
    if not hasattr(context, "_backfill_created"):
        context._backfill_created = {
            "observation_ids": [],
            "note_ids": [],
            "analysis_method_ids": [],
            "sample_ids": [],
            "field_activity_ids": [],
            "field_event_ids": [],
            "nma_radionuclide_ids": [],
            "nma_minor_trace_ids": [],
            "nma_sampleinfo_ids": [],
            "location_ids": [],
            "well_ids": [],
        }


def _ensure_well(context: Context):
    """Ensure context.objects['wells'] has at least one well.

    When running without DROP_AND_REBUILD_DB the before_all fixture doesn't
    create wells.  This helper creates a minimal Location → Thing chain so
    the chemistry-backfill steps can link NMA_Chemistry_SampleInfo rows to a
    Thing.
    """
    if not hasattr(context, "objects"):
        context.objects = {}
    wells = context.objects.get("wells") or []
    if wells:
        existing_well = wells[0]
        existing_well_id = getattr(existing_well, "id", None)
        if existing_well_id is not None:
            with session_ctx() as session:
                persisted = session.execute(
                    select(Thing).where(Thing.id == existing_well_id)
                ).scalar_one_or_none()
            if persisted is not None:
                return  # already have a persisted well
        context.objects["wells"] = []

    _ensure_backfill_tracking(context)
    with session_ctx() as session:
        loc = Location(
            point="POINT(-107.949533 33.809665)",
            elevation=2464.9,
            release_status="draft",
        )
        session.add(loc)
        session.flush()
        context._backfill_created["location_ids"].append(loc.id)

        well = Thing(
            name="CHEM-TEST-0001",
            first_visit_date="2023-03-03",
            thing_type="water well",
            release_status="draft",
            well_depth=10,
            hole_depth=10,
        )
        session.add(well)
        session.flush()
        context._backfill_created["well_ids"].append(well.id)

        assoc = LocationThingAssociation(location=loc, thing=well)
        assoc.effective_start = "2025-02-01T00:00:00Z"
        session.add(assoc)
        session.commit()
        session.refresh(well)

        if "wells" not in context.objects:
            context.objects["wells"] = []
        context.objects["wells"].append(well)


def _parse_table_value(raw: str):
    """Parse a table cell value, handling 'null' and numeric coercion."""
    if raw.strip().lower() == "null":
        return None
    return raw.strip()


def _get_observation_by_globalid(session, global_id: str) -> Observation:
    obs = session.execute(
        select(Observation).where(
            Observation.nma_pk_chemistryresults == global_id.lower()
        )
    ).scalar_one_or_none()
    assert (
        obs is not None
    ), f"No Observation found with nma_pk_chemistryresults='{global_id.lower()}'"
    return obs


# ---------------------------------------------------------------------------
# GIVEN steps
# ---------------------------------------------------------------------------
@given("a database session is available")
def step_given_db_session(context: Context):
    """Verify session_ctx works and init context attributes."""
    _ensure_backfill_tracking(context)
    with session_ctx() as session:
        assert session is not None, "Database session should be available"
    context.backfill_result = None
    context.chemistry_type = None


@given("legacy NMA_Radionuclides records exist in the database")
def step_given_legacy_radionuclides_exist(context: Context):
    """Marker step — sets chemistry_type on context."""
    _ensure_backfill_tracking(context)
    context.chemistry_type = "Radionuclides"


@given("legacy NMA_MinorTraceChemistry records exist in the database")
def step_given_legacy_minor_trace_exist(context: Context):
    """Marker step — sets chemistry_type on context."""
    _ensure_backfill_tracking(context)
    context.chemistry_type = "MinorTraceChemistry"


@given(
    'lexicon terms exist for parameter_name, unit, analysis_method_type, and sample_matrix "water"'
)
def step_given_lexicon_terms_exist(context: Context):
    """Fail-fast check that critical lexicon terms are seeded.

    Also seeds test-only analyte names so the backfill can create
    Parameter records without requiring production lexicon data.
    """
    _ensure_backfill_tracking(context)
    with session_ctx() as session:
        from db.lexicon import LexiconTerm

        # Terms that must already exist (seeded by init_lexicon)
        required_terms = ["water", "Chemistry Observation"]
        # Add unit terms based on chemistry type
        if getattr(context, "chemistry_type", None) == "Radionuclides":
            required_terms.append("pCi/L")

        for term in required_terms:
            row = session.execute(
                select(LexiconTerm).where(LexiconTerm.term == term)
            ).scalar_one_or_none()
            assert row is not None, (
                f"Required lexicon term '{term}' not found. "
                "Ensure init_lexicon() ran during before_all."
            )

        # Test-only analyte names used by scenarios — seed if absent.
        # In production these would be pre-seeded via a vocabulary
        # preparation step.
        test_analytes = (
            # Radionuclides
            "GB",
            "Uranium",
            "GA",
            "Ra228",
            "Uranium-238",
            "Radium-226",
            # Minor/Trace
            "Arsenic",
            "Boron",
            "Lead",
            "Copper",
            "Zinc",
            "Iron",
            "Cadmium",
            # Shared
            "Nitrate",
            "Unknown",
            # Units
            "ug/L",
        )
        for analyte in test_analytes:
            existing = session.execute(
                select(LexiconTerm).where(LexiconTerm.term == analyte)
            ).scalar_one_or_none()
            if existing is None:
                session.add(LexiconTerm(term=analyte, definition=analyte))
        session.commit()


@given("a legacy NMA_Radionuclides record exists with:")
def step_given_single_radionuclide(context: Context):
    """Create a single NMA_Radionuclides row from a vertical Behave table."""
    _ensure_backfill_tracking(context)
    fields = {row["field"]: _parse_table_value(row["value"]) for row in context.table}
    _create_radionuclide_from_fields(context, fields)


@given("legacy NMA_Radionuclides records exist with:")
def step_given_multi_radionuclides(context: Context):
    """Create multiple NMA_Radionuclides rows from a horizontal Behave table."""
    _ensure_backfill_tracking(context)
    for row in context.table:
        fields = {
            heading: _parse_table_value(row[heading])
            for heading in context.table.headings
        }
        _create_radionuclide_from_fields(context, fields)


@given("a legacy NMA_MinorTraceChemistry record exists with:")
def step_given_single_minor_trace(context: Context):
    """Create a single NMA_MinorTraceChemistry row from a vertical Behave table."""
    _ensure_backfill_tracking(context)
    fields = {row["field"]: _parse_table_value(row["value"]) for row in context.table}
    _create_minor_trace_from_fields(context, fields)


@given("legacy NMA_MinorTraceChemistry records exist with:")
def step_given_multi_minor_trace(context: Context):
    """Create multiple NMA_MinorTraceChemistry rows from a horizontal Behave table."""
    _ensure_backfill_tracking(context)
    for row in context.table:
        fields = {
            heading: _parse_table_value(row[heading])
            for heading in context.table.headings
        }
        _create_minor_trace_from_fields(context, fields)


@given("a legacy Chemistry_SampleInfo record exists with:")
def step_given_sampleinfo(context: Context):
    """Create an NMA_Chemistry_SampleInfo row from a vertical Behave table."""
    _ensure_backfill_tracking(context)
    _ensure_well(context)
    fields = {row["field"]: _parse_table_value(row["value"]) for row in context.table}

    with session_ctx() as session:
        well = context.objects["wells"][0]
        well = session.merge(well)

        sampleinfo = NMA_Chemistry_SampleInfo(
            thing_id=well.id,
            nma_sample_pt_id=fields.get("SamplePtID"),
            nma_sample_point_id=fields.get("SamplePointID", "UNKNOWN"),
        )
        session.add(sampleinfo)
        session.commit()
        session.refresh(sampleinfo)
        context._backfill_created["nma_sampleinfo_ids"].append(sampleinfo.id)

        # Store for later use
        if not hasattr(context, "_sampleinfo_map"):
            context._sampleinfo_map = {}
        context._sampleinfo_map[fields["SamplePtID"]] = sampleinfo.id


@given('a Sample record exists with nma_pk_chemistrysample "{sample_pt_id}"')
def step_given_sample_with_chemistry_key(context: Context, sample_pt_id: str):
    """Create FieldEvent → FieldActivity → Sample chain linked to first well."""
    _ensure_backfill_tracking(context)
    _ensure_well(context)

    with session_ctx() as session:
        well = context.objects["wells"][0]
        well = session.merge(well)

        fe = FieldEvent(
            thing_id=well.id,
            event_date=datetime(2005, 1, 1, tzinfo=timezone.utc),
            release_status="draft",
        )
        session.add(fe)
        session.flush()
        context._backfill_created["field_event_ids"].append(fe.id)

        fa = FieldActivity(
            field_event_id=fe.id,
            activity_type="water chemistry",
            release_status="draft",
        )
        session.add(fa)
        session.flush()
        context._backfill_created["field_activity_ids"].append(fa.id)

        sample = Sample(
            field_activity_id=fa.id,
            sample_date=datetime(2005, 1, 1, tzinfo=timezone.utc),
            sample_name=f"CHEM-{uuid.uuid4().hex[:8]}",
            sample_matrix="water",
            sample_method="Estimated",
            qc_type="Normal",
            nma_pk_chemistrysample=sample_pt_id,
            release_status="draft",
        )
        session.add(sample)
        session.commit()
        session.refresh(sample)
        context._backfill_created["sample_ids"].append(sample.id)


# ---------------------------------------------------------------------------
# WHEN steps
# ---------------------------------------------------------------------------
def _snapshot_analysis_method_ids() -> set[int]:
    """Return the set of all AnalysisMethod IDs that exist before the backfill."""
    with session_ctx() as session:
        return {row[0] for row in session.execute(select(AnalysisMethod.id)).all()}


def _track_created_analysis_methods(context: Context, pre_ids: set[int]):
    """Record only AnalysisMethod IDs that were actually created by the backfill."""
    _ensure_backfill_tracking(context)
    with session_ctx() as session:
        post_ids = {row[0] for row in session.execute(select(AnalysisMethod.id)).all()}
    new_ids = post_ids - pre_ids
    context._backfill_created["analysis_method_ids"] = list(new_ids)


@when("I run the Radionuclides backfill job")
def step_when_run_backfill(context: Context):
    """Execute the backfill and store the result on context."""
    from transfers.backfill.chemistry_backfill import backfill_radionuclides

    pre_ids = _snapshot_analysis_method_ids()
    context.backfill_result = backfill_radionuclides()
    _track_created_analysis_methods(context, pre_ids)


@when("I run the Radionuclides backfill job again")
def step_when_run_backfill_again(context: Context):
    """Re-run to verify idempotency."""
    from transfers.backfill.chemistry_backfill import backfill_radionuclides

    pre_ids = _snapshot_analysis_method_ids()
    context.backfill_result = backfill_radionuclides()
    _track_created_analysis_methods(context, pre_ids)


@when("I run the Minor Trace Chemistry backfill job")
def step_when_run_minor_trace_backfill(context: Context):
    """Execute the minor trace chemistry backfill and store the result."""
    from transfers.backfill.chemistry_backfill import backfill_minor_trace_chemistry

    pre_ids = _snapshot_analysis_method_ids()
    context.backfill_result = backfill_minor_trace_chemistry()
    _track_created_analysis_methods(context, pre_ids)


@when("I run the Minor Trace Chemistry backfill job again")
def step_when_run_minor_trace_backfill_again(context: Context):
    """Re-run to verify idempotency."""
    from transfers.backfill.chemistry_backfill import backfill_minor_trace_chemistry

    pre_ids = _snapshot_analysis_method_ids()
    context.backfill_result = backfill_minor_trace_chemistry()
    _track_created_analysis_methods(context, pre_ids)


# ---------------------------------------------------------------------------
# THEN steps
# ---------------------------------------------------------------------------
@then(
    'exactly {n:d} Observation record should exist with nma_pk_chemistryresults "{global_id}"'
)
def step_then_observation_count(context: Context, n: int, global_id: str):
    with session_ctx() as session:
        count = session.execute(
            select(Observation).where(
                Observation.nma_pk_chemistryresults == global_id.lower()
            )
        ).all()
        assert (
            len(count) == n
        ), f"Expected {n} Observation(s) for GlobalID {global_id}, found {len(count)}"
        if len(count) == 1:
            context._last_observation = count[0][0]


@then(
    'the Observation should reference the Sample with nma_pk_chemistrysample "{sample_pt_id}"'
)
def step_then_observation_refs_sample(context: Context, sample_pt_id: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        sample = session.get(Sample, obs.sample_id)
        assert sample is not None, "Observation must reference a Sample"
        assert sample.nma_pk_chemistrysample == sample_pt_id, (
            f"Expected Sample.nma_pk_chemistrysample={sample_pt_id}, "
            f"got {sample.nma_pk_chemistrysample}"
        )


@then('the Observation should set observation_datetime to "{date_str}"')
def step_then_observation_datetime(context: Context, date_str: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        dt = obs.observation_datetime
        # Normalize to UTC for comparison (pg may return in server tz)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        actual_date = dt.strftime("%Y-%m-%d")
        assert (
            actual_date == date_str
        ), f"Expected observation_datetime={date_str}, got {actual_date}"


@then("the Observation should set value to {value}")
def step_then_observation_value(context: Context, value: str):
    obs = context._last_observation
    expected = float(value)
    with session_ctx() as session:
        obs = session.merge(obs)
        assert obs.value == expected, f"Expected value={expected}, got {obs.value}"


@then('the Observation should set unit to "{unit}"')
def step_then_observation_unit(context: Context, unit: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        assert obs.unit == unit, f"Expected unit={unit}, got {obs.unit}"


@then(
    'a Parameter record should exist with parameter_name "{name}" and matrix "{matrix}"'
)
def step_then_parameter_exists(context: Context, name: str, matrix: str):
    with session_ctx() as session:
        param = session.execute(
            select(Parameter).where(
                Parameter.parameter_name == name, Parameter.matrix == matrix
            )
        ).scalar_one_or_none()
        assert (
            param is not None
        ), f"No Parameter found with parameter_name='{name}' and matrix='{matrix}'"
        context._last_parameter = param


@then(
    'the Observation should reference the Parameter with parameter_name "{name}" and matrix "{matrix}"'
)
def step_then_observation_refs_parameter(context: Context, name: str, matrix: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        param = session.get(Parameter, obs.parameter_id)
        assert param is not None, "Observation must reference a Parameter"
        assert (
            param.parameter_name == name
        ), f"Expected parameter_name='{name}', got '{param.parameter_name}'"
        assert (
            param.matrix == matrix
        ), f"Expected matrix='{matrix}', got '{param.matrix}'"


@then('the Observation should set analysis_method_name to "{method}"')
def step_then_observation_analysis_method(context: Context, method: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        assert (
            obs.analysis_method_id is not None
        ), "Observation should have an analysis_method_id"
        am = session.get(AnalysisMethod, obs.analysis_method_id)
        assert am is not None, "AnalysisMethod should exist"
        assert (
            am.analysis_method_name == method
        ), f"Expected analysis_method_name='{method}', got '{am.analysis_method_name}'"


@then("the Observation should set uncertainty to {value}")
def step_then_observation_uncertainty(context: Context, value: str):
    obs = context._last_observation
    expected = float(value)
    with session_ctx() as session:
        obs = session.merge(obs)
        assert (
            obs.uncertainty == expected
        ), f"Expected uncertainty={expected}, got {obs.uncertainty}"


@then('the Observation should set analysis_agency to "{agency}"')
def step_then_observation_analysis_agency(context: Context, agency: str):
    obs = context._last_observation
    with session_ctx() as session:
        obs = session.merge(obs)
        assert (
            obs.analysis_agency == agency
        ), f"Expected analysis_agency='{agency}', got '{obs.analysis_agency}'"


# --- GlobalID-variant steps ---
@then(
    'the Observation for GlobalID "{global_id}" should reference the Sample with nma_pk_chemistrysample "{sample_pt_id}"'
)
def step_then_obs_by_gid_refs_sample(
    context: Context, global_id: str, sample_pt_id: str
):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        sample = session.get(Sample, obs.sample_id)
        assert sample is not None
        assert sample.nma_pk_chemistrysample == sample_pt_id, (
            f"Expected Sample.nma_pk_chemistrysample={sample_pt_id}, "
            f"got {sample.nma_pk_chemistrysample}"
        )


@then(
    'the Observation for GlobalID "{global_id}" should reference the Thing associated with that Sample'
)
def step_then_obs_by_gid_refs_thing(context: Context, global_id: str):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        sample = session.get(Sample, obs.sample_id)
        assert sample is not None
        fa = sample.field_activity
        assert fa is not None, "Sample must have a field_activity"
        fe = fa.field_event
        assert fe is not None, "FieldActivity must have a field_event"
        assert fe.thing_id is not None, "FieldEvent must reference a Thing"


@then(
    'the Observation for GlobalID "{global_id}" should set analysis_method_name to "{method}"'
)
def step_then_obs_by_gid_analysis_method(context: Context, global_id: str, method: str):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        assert obs.analysis_method_id is not None
        am = session.get(AnalysisMethod, obs.analysis_method_id)
        assert am is not None
        assert (
            am.analysis_method_name == method
        ), f"Expected analysis_method_name='{method}', got '{am.analysis_method_name}'"


@then(
    'the Observation for GlobalID "{global_id}" should reference the Parameter with parameter_name "{name}" and matrix "{matrix}"'
)
def step_then_obs_by_gid_refs_parameter(
    context: Context, global_id: str, name: str, matrix: str
):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        param = session.get(Parameter, obs.parameter_id)
        assert param is not None
        assert param.parameter_name == name
        assert param.matrix == matrix


@then('the Observation for GlobalID "{global_id}" should set detect_flag to {flag}')
def step_then_obs_by_gid_detect_flag(context: Context, global_id: str, flag: str):
    expected = flag.lower() == "true"
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        assert (
            obs.detect_flag == expected
        ), f"Expected detect_flag={expected}, got {obs.detect_flag}"


@then(
    'the Observation for GlobalID "{global_id}" should not store SamplePointID, OBJECTID, or WCLab_ID'
)
def step_then_obs_by_gid_no_extra_columns(context: Context, global_id: str):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        for attr in ("nma_sample_point_id", "nma_object_id", "nma_wclab_id"):
            assert not hasattr(
                obs, attr
            ), f"Observation should not have attribute '{attr}'"


@then(
    'the Observation for GlobalID "{global_id}" should not store SamplePointID, OBJECTID, WCLab_ID, Volume, or VolumeUnit'
)
def step_then_obs_by_gid_no_extra_columns_extended(context: Context, global_id: str):
    with session_ctx() as session:
        obs = _get_observation_by_globalid(session, global_id)
        for attr in (
            "nma_sample_point_id",
            "nma_object_id",
            "nma_wclab_id",
            "volume",
            "volume_unit",
        ):
            assert not hasattr(
                obs, attr
            ), f"Observation should not have attribute '{attr}'"


# --- Sample volume steps ---
@then("the Sample should set volume to {value}")
def step_then_sample_volume(context: Context, value: str):
    expected = float(value)
    scenario_sample_ids = context._backfill_created.get("sample_ids", [])
    assert scenario_sample_ids, "No sample_ids tracked for this scenario"
    with session_ctx() as session:
        sample = (
            session.execute(select(Sample).where(Sample.id.in_(scenario_sample_ids)))
            .scalars()
            .first()
        )
        assert sample is not None, "No Sample found for this scenario"
        assert (
            sample.volume == expected
        ), f"Expected volume={expected}, got {sample.volume}"


@then('the Sample should set volume_unit to "{unit}"')
def step_then_sample_volume_unit(context: Context, unit: str):
    scenario_sample_ids = context._backfill_created.get("sample_ids", [])
    assert scenario_sample_ids, "No sample_ids tracked for this scenario"
    with session_ctx() as session:
        sample = (
            session.execute(select(Sample).where(Sample.id.in_(scenario_sample_ids)))
            .scalars()
            .first()
        )
        assert sample is not None, "No Sample found for this scenario"
        assert (
            sample.volume_unit == unit
        ), f"Expected volume_unit='{unit}', got '{sample.volume_unit}'"


# --- Notes steps ---
@then("a Notes record should exist with:")
def step_then_notes_exist(context: Context):
    fields = {row["field"]: row["value"] for row in context.table}
    target_table = fields["target_table"]
    note_type = fields["note_type"]
    content = fields["content"]

    # Resolve dynamic target_id
    target_id_raw = fields["target_id"]
    if target_id_raw.startswith("(observation.id for GlobalID"):
        gid = target_id_raw.split("GlobalID")[1].strip().rstrip(")")
        with session_ctx() as session:
            obs = _get_observation_by_globalid(session, gid)
            target_id = obs.id
    else:
        target_id = int(target_id_raw)

    with session_ctx() as session:
        note = session.execute(
            select(Notes).where(
                Notes.target_id == target_id,
                Notes.target_table == target_table,
                Notes.note_type == note_type,
                Notes.content == content,
            )
        ).scalar_one_or_none()
        assert note is not None, (
            f"No Notes found with target_table={target_table}, target_id={target_id}, "
            f"note_type={note_type}, content={content}"
        )


# --- Orphan prevention steps ---
@then(
    "the backfill job should report {n:d} skipped record due to missing Sample linkage (SamplePtID)"
)
def step_then_skipped_orphans(context: Context, n: int):
    assert context.backfill_result is not None, "Backfill result not found on context"
    assert (
        context.backfill_result.skipped_orphans == n
    ), f"Expected {n} skipped orphans, got {context.backfill_result.skipped_orphans}"


@then('no Observation record should exist with nma_pk_chemistryresults "{global_id}"')
def step_then_no_observation(context: Context, global_id: str):
    with session_ctx() as session:
        count = session.execute(
            select(Observation).where(
                Observation.nma_pk_chemistryresults == global_id.lower()
            )
        ).all()
        assert (
            len(count) == 0
        ), f"Expected 0 Observations for GlobalID {global_id}, found {len(count)}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _create_radionuclide_from_fields(context: Context, fields: dict):
    """Create NMA_Chemistry_SampleInfo (if needed) and NMA_Radionuclides row."""
    _ensure_well(context)
    global_id = fields.get("GlobalID")
    sample_pt_id = fields.get("SamplePtID")

    with session_ctx() as session:
        well = context.objects["wells"][0]
        well = session.merge(well)

        # Get or create SampleInfo for this SamplePtID
        sampleinfo = session.execute(
            select(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_sample_pt_id == sample_pt_id
            )
        ).scalar_one_or_none()

        if sampleinfo is None:
            sampleinfo = NMA_Chemistry_SampleInfo(
                thing_id=well.id,
                nma_sample_pt_id=sample_pt_id,
                nma_sample_point_id=fields.get("SamplePointID", "UNKNOWN"),
            )
            session.add(sampleinfo)
            session.flush()
            context._backfill_created["nma_sampleinfo_ids"].append(sampleinfo.id)

        # Parse analysis date (store as UTC so the backfill's tz handling is a no-op)
        analysis_date = None
        if fields.get("AnalysisDate"):
            analysis_date = datetime.strptime(
                fields["AnalysisDate"], "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)

        # Parse numeric fields
        sample_value = (
            float(fields["SampleValue"]) if fields.get("SampleValue") else None
        )
        uncertainty_val = (
            float(fields["Uncertainty"]) if fields.get("Uncertainty") else None
        )
        volume_val = int(fields["Volume"]) if fields.get("Volume") else None

        rad = NMA_Radionuclides(
            chemistry_sample_info_id=sampleinfo.id,
            nma_global_id=global_id,
            nma_sample_pt_id=sample_pt_id,
            nma_sample_point_id=fields.get("SamplePointID"),
            nma_object_id=int(fields["OBJECTID"]) if fields.get("OBJECTID") else None,
            nma_wclab_id=fields.get("WCLab_ID"),
            analyte=fields.get("Analyte"),
            symbol=fields.get("Symbol"),
            sample_value=sample_value,
            units=fields.get("Units"),
            uncertainty=uncertainty_val,
            analysis_method=fields.get("AnalysisMethod"),
            analysis_date=analysis_date,
            notes=fields.get("Notes"),
            volume=volume_val,
            volume_unit=fields.get("VolumeUnit"),
            analyses_agency=fields.get("AnalysesAgency"),
        )
        session.add(rad)
        session.commit()
        session.refresh(rad)
        context._backfill_created["nma_radionuclide_ids"].append(rad.id)


def _create_minor_trace_from_fields(context: Context, fields: dict):
    """Create NMA_Chemistry_SampleInfo (if needed) and NMA_MinorTraceChemistry row."""
    _ensure_well(context)
    global_id = fields.get("GlobalID")
    sample_pt_id = fields.get("SamplePtID")

    with session_ctx() as session:
        well = context.objects["wells"][0]
        well = session.merge(well)

        # Get or create SampleInfo for this SamplePtID
        sampleinfo = session.execute(
            select(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_sample_pt_id == sample_pt_id
            )
        ).scalar_one_or_none()

        if sampleinfo is None:
            sampleinfo = NMA_Chemistry_SampleInfo(
                thing_id=well.id,
                nma_sample_pt_id=sample_pt_id,
                nma_sample_point_id=fields.get("SamplePointID", "UNKNOWN"),
            )
            session.add(sampleinfo)
            session.flush()
            context._backfill_created["nma_sampleinfo_ids"].append(sampleinfo.id)

        # Parse analysis date as a plain date to match the Date column type
        analysis_date = None
        if fields.get("AnalysisDate"):
            analysis_date = datetime.strptime(
                fields["AnalysisDate"], "%Y-%m-%d"
            ).date()

        # Parse numeric fields
        sample_value = (
            float(fields["SampleValue"]) if fields.get("SampleValue") else None
        )
        uncertainty_val = (
            float(fields["Uncertainty"]) if fields.get("Uncertainty") else None
        )
        volume_val = int(fields["Volume"]) if fields.get("Volume") else None

        mtc = NMA_MinorTraceChemistry(
            chemistry_sample_info_id=sampleinfo.id,
            nma_global_id=global_id,
            nma_sample_point_id=fields.get("SamplePointID", "UNKNOWN"),
            nma_wclab_id=fields.get("WCLab_ID"),
            analyte=fields.get("Analyte"),
            symbol=fields.get("Symbol"),
            sample_value=sample_value,
            units=fields.get("Units"),
            uncertainty=uncertainty_val,
            analysis_method=fields.get("AnalysisMethod"),
            analysis_date=analysis_date,
            notes=fields.get("Notes"),
            volume=volume_val,
            volume_unit=fields.get("VolumeUnit"),
            analyses_agency=fields.get("AnalysesAgency"),
        )
        session.add(mtc)
        session.commit()
        session.refresh(mtc)
        context._backfill_created["nma_minor_trace_ids"].append(mtc.id)


# ============= EOF =============================================
