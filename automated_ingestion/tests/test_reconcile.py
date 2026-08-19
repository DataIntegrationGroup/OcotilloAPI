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
Reconciliation decisions.

The rule that matters: never pick a winner among candidates. Ingestion does not
create wells and must not choose between two plausible ones.
"""

from automated_ingestion.sources.san_acacia.reconcile import (
    MatchKind,
    ThingCandidate,
    VendorPoint,
    format_report,
    match_point,
    reconcile,
)

POINT = VendorPoint(monitoring_point_id=39, name="SO-0125")


def test_exact_name_match():
    match = match_point(POINT, [ThingCandidate(thing_id=7, name="SO-0125")])
    assert match.kind is MatchKind.NAME
    assert match.thing_id == 7
    assert not match.needs_a_human


def test_name_match_ignores_case_spacing_and_punctuation():
    # One identifier written three ways. Still exact on significant characters.
    for written in ("so 0125", "SO0125", " so-0125 "):
        match = match_point(POINT, [ThingCandidate(thing_id=7, name=written)])
        assert match.thing_id == 7, written


def test_adjacent_identifier_is_not_a_match():
    # Normalization must not become fuzziness: SO-0126 is a different well.
    match = match_point(POINT, [ThingCandidate(thing_id=7, name="SO-0126")])
    assert match.kind is MatchKind.UNMATCHED


def test_external_id_match_when_the_name_differs():
    match = match_point(
        POINT,
        [ThingCandidate(thing_id=9, name="Renamed Well", external_ids=("SO-0125",))],
    )
    assert match.kind is MatchKind.EXTERNAL_ID
    assert match.thing_id == 9


def test_name_wins_over_external_id():
    # The name is the identifier the Bureau uses now; a link records an
    # association someone made earlier, which may be stale.
    match = match_point(
        POINT,
        [
            ThingCandidate(thing_id=7, name="SO-0125"),
            ThingCandidate(thing_id=9, name="Other", external_ids=("SO-0125",)),
        ],
    )
    assert match.thing_id == 7


def test_two_wells_with_the_same_name_are_ambiguous():
    # Duplicate rows exist in this database. Picking one is exactly the
    # judgement that must not be automated.
    match = match_point(
        POINT,
        [
            ThingCandidate(thing_id=7, name="SO-0125"),
            ThingCandidate(thing_id=8, name="SO-0125"),
        ],
    )
    assert match.kind is MatchKind.AMBIGUOUS
    assert match.thing_id is None
    assert match.candidates == (7, 8)
    assert match.needs_a_human


def test_no_candidate_is_unmatched_not_created():
    match = match_point(POINT, [])
    assert match.kind is MatchKind.UNMATCHED
    assert match.thing_id is None


class TestReport:
    def _report(self):
        points = [
            VendorPoint(39, "SO-0125"),
            VendorPoint(40, "SO-0131"),
            VendorPoint(41, "SO-0140"),
        ]
        candidates = [
            ThingCandidate(1, "SO-0125"),
            ThingCandidate(2, "SO-0131"),
            ThingCandidate(3, "SO-0131"),
        ]
        return reconcile(points, candidates)

    def test_counts_split_by_outcome(self):
        report = self._report()
        assert len(report.matched) == 1
        assert len(report.ambiguous) == 1
        assert len(report.unmatched) == 1

    def test_not_ready_while_anything_needs_a_human(self):
        # A partial load produces a series that looks complete and is not.
        assert self._report().ready is False

    def test_ready_only_when_everything_resolves(self):
        report = reconcile([VendorPoint(39, "SO-0125")], [ThingCandidate(1, "SO-0125")])
        assert report.ready is True

    def test_empty_input_is_not_ready(self):
        # Nothing to reconcile is not the same as everything reconciled.
        assert reconcile([], []).ready is False

    def test_report_names_the_points_needing_attention(self):
        text = format_report(self._report())
        assert "SO-0131" in text and "SO-0140" in text


# ============= EOF =============================================
