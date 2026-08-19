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
Matching Diver-HUB monitoring points to Ocotillo wells.

Ingestion never creates a well. A vendor point that matches nothing is a
question for a person, not a row to invent -- the duplicate Geographic Area
groups elsewhere in this database are the standing reminder that "looks like a
new record" is not proof.

So this decides, per point, one of three things: exactly one candidate
(matched), more than one (ambiguous, escalate), or none (unmatched, escalate).
It never picks a winner among candidates. Choosing between two plausible wells
is precisely the judgement that should not be automated.

**Matching is on identifiers only.** The plan called for coordinate proximity as
a third signal; the live ``MonitoringPoint`` payload is ``{id, name}`` and
carries no coordinates, so there is nothing to compare. That removes the one
fuzzy signal and leaves two exact ones, which is a better position to be in --
every match here is defensible rather than probabilistic.

The functions are pure: they take vendor points and candidate rows and return a
report. Loading the candidates is the caller's job, so the decision logic is
testable without a database.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class MatchKind(str, Enum):
    """How a point was matched, or why it was not."""

    NAME = "matched-by-name"
    EXTERNAL_ID = "matched-by-external-id"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


@dataclass(frozen=True)
class VendorPoint:
    """A monitoring point as Diver-HUB reports it."""

    monitoring_point_id: int
    name: str


@dataclass(frozen=True)
class ThingCandidate:
    """An Ocotillo well that might be the same well."""

    thing_id: int
    name: str
    external_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Match:
    """What was decided about one vendor point."""

    point: VendorPoint
    kind: MatchKind
    thing_id: int | None = None
    candidates: tuple[int, ...] = ()

    @property
    def needs_a_human(self) -> bool:
        return self.kind in (MatchKind.AMBIGUOUS, MatchKind.UNMATCHED)


@dataclass
class ReconciliationReport:
    """The whole picture, for a person to read before anything is written."""

    matches: list[Match] = field(default_factory=list)

    @property
    def matched(self) -> list[Match]:
        return [m for m in self.matches if not m.needs_a_human]

    @property
    def ambiguous(self) -> list[Match]:
        return [m for m in self.matches if m.kind is MatchKind.AMBIGUOUS]

    @property
    def unmatched(self) -> list[Match]:
        return [m for m in self.matches if m.kind is MatchKind.UNMATCHED]

    @property
    def ready(self) -> bool:
        """True when every point resolved to exactly one well.

        Deliberately strict. A partial run that ingests the wells it recognised
        and quietly skips the rest produces a series that looks complete and is
        not.
        """
        return bool(self.matches) and not any(m.needs_a_human for m in self.matches)


def _normalize(value: str) -> str:
    """Reduce a well identifier to its significant characters.

    Case, spacing and punctuation are dropped, so ``SO-0125``, ``so 0125`` and
    ``SO0125`` compare equal -- one identifier written three ways.

    This is still exact matching, not similarity: every significant character
    must agree, so ``SO-0126`` remains a different well. The distinction matters
    because a fuzzy matcher here would eventually merge two real wells, and the
    whole point of this module is that it never chooses between candidates.
    """
    return "".join(c for c in (value or "") if c.isalnum()).upper()


def match_point(
    point: VendorPoint,
    candidates: Iterable[ThingCandidate],
    use_external_ids: bool = False,
) -> Match:
    """Decide one point against the wells it might be.

    ``use_external_ids`` is off by default, for a specific reason.
    ``thing_id_link`` holds identifiers from several organizations that disagree
    with each other. In staging, ``SO-0131`` carries NMBGMR ``BRN-E04B
    (shallow)`` plus an unattributed ``BRN-E04A``, while ``SO-0132`` carries
    NMBGMR ``BRN-E04A (deep)`` plus an unattributed ``BRN-E04B`` -- the two
    sources swap which physical well is A and which is B.

    Matching ``BRN-E04A`` against that returns a single confident hit on
    SO-0131, contradicting NMBGMR, because the parenthetical suffix stops the
    collision registering as ambiguous. A wrong answer delivered confidently is
    worse than no answer.

    It costs nothing today: all 38 Diver-HUB points match Ocotillo wells by name.
    """
    target = _normalize(point.name)

    by_name = [c for c in candidates if _normalize(c.name) == target]
    by_external = (
        [
            c
            for c in candidates
            if any(_normalize(x) == target for x in c.external_ids) and c not in by_name
        ]
        if use_external_ids
        else []
    )

    # Name first: it is the identifier the Bureau uses, and an external id link
    # is a record of an association someone made, which may be older.
    hits = by_name or by_external
    kind = MatchKind.NAME if by_name else MatchKind.EXTERNAL_ID

    if len(hits) == 1:
        return Match(point=point, kind=kind, thing_id=hits[0].thing_id)
    if len(hits) > 1:
        return Match(
            point=point,
            kind=MatchKind.AMBIGUOUS,
            candidates=tuple(c.thing_id for c in hits),
        )
    return Match(point=point, kind=MatchKind.UNMATCHED)


def reconcile(
    points: Iterable[VendorPoint],
    candidates: Iterable[ThingCandidate],
    use_external_ids: bool = False,
) -> ReconciliationReport:
    """Match every vendor point, reporting rather than resolving."""
    candidate_list = list(candidates)
    report = ReconciliationReport()
    for point in points:
        report.matches.append(
            match_point(point, candidate_list, use_external_ids=use_external_ids)
        )
    return report


def format_report(report: ReconciliationReport) -> str:
    """Human-readable summary. This is the deliverable of task 3.2."""
    lines = [
        f"Vendor points     : {len(report.matches)}",
        f"  matched         : {len(report.matched)}",
        f"  ambiguous       : {len(report.ambiguous)}",
        f"  unmatched       : {len(report.unmatched)}",
        "",
    ]
    if report.ready:
        lines.append("Every point resolved to exactly one well.")
        return "\n".join(lines)

    if report.ambiguous:
        lines.append("Ambiguous -- more than one well matches. Do not auto-merge:")
        for match in report.ambiguous:
            ids = ", ".join(str(c) for c in match.candidates)
            lines.append(f"  {match.point.name:<12} thing ids: {ids}")
        lines.append("")
    if report.unmatched:
        lines.append("Unmatched -- no well found. Ingestion will not create one:")
        for match in report.unmatched:
            lines.append(
                f"  {match.point.name:<12} (vendor id {match.point.monitoring_point_id})"
            )
        lines.append("")
    lines.append("Resolve these before loading; a partial load looks complete.")
    return "\n".join(lines)


# ============= EOF =============================================
