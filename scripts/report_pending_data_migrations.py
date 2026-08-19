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
Report data migrations registered but not yet applied to this environment.

Deploys run `alembic upgrade head` and nothing else, deliberately: a data
migration changes content rather than structure, is often irreversible -- a
deletion has no downgrade -- and may be slow enough to hold a deploy hostage.
Applying one is a decision, and `data_migrations.yml` is where it is made.

The cost of that choice is that a merged migration can sit unnoticed. This
closes the gap without moving the decision: it reports, and never applies.

Exits zero even when migrations are pending. A deploy that succeeded should not
report failure because a separate, deliberate action has not been taken yet --
people learn to ignore a pipeline that cries wolf. The finding surfaces as a
GitHub warning annotation and in the job summary instead.
"""

import os


def main() -> int:
    from data_migrations.runner import get_status
    from db.engine import session_ctx

    try:
        with session_ctx() as session:
            statuses = get_status(session)
    except Exception as exc:  # noqa: BLE001 - never fail a good deploy over this
        print(f"::warning::Could not read data migration status: {exc}")
        return 0

    pending = [s for s in statuses if s.applied_count == 0 and not s.is_repeatable]
    applied = len(statuses) - len(pending)

    summary = [
        "## Data migrations",
        "",
        f"{applied} applied, **{len(pending)} pending**.",
        "",
    ]

    if pending:
        for status in pending:
            print(
                f"::warning::Data migration not applied: {status.id} "
                f"({status.name}). Run it from the Data Migrations workflow."
            )
        summary += [
            "| id | name |",
            "| --- | --- |",
            *[f"| `{s.id}` | {s.name} |" for s in pending],
            "",
            "These do **not** run on deploy. Apply them from the "
            "**Data Migrations** workflow when you intend to.",
        ]
    else:
        summary.append("Nothing pending.")

    print("\n".join(summary))

    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as handle:
            handle.write("\n".join(summary) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ============= EOF =============================================
