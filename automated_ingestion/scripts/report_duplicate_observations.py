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
Report duplicate transducer observations before the unique constraint migration.

Does what ``sql/find_duplicate_observations.sql`` does, without needing ``psql``
or a password: it connects through the Cloud SQL connector with IAM
authentication, so the credential is your own gcloud login and nothing is
stored.

    gcloud auth application-default login
    uv run --group ingestion python -m \\
        automated_ingestion.scripts.report_duplicate_observations \\
        --instance waterdatainitiative-271000:us-west4:dataservices \\
        --database ocotillo-staging

You need a database login. Being a project owner is not enough -- Cloud SQL
requires the principal to exist as a database user:

    gcloud sql users create YOUR_EMAIL --instance=dataservices \\
        --type=cloud_iam_user --project=waterdatainitiative-271000

Read-only. It counts and reports; deciding what to do about duplicates is a
judgement about the data, not something a script should make.
"""

import argparse
import sys

DUPLICATE_GROUPS = """
SELECT deployment_id, parameter_id, observation_datetime,
       count(*) AS copies, count(DISTINCT value) AS distinct_values
FROM transducer_observation
GROUP BY deployment_id, parameter_id, observation_datetime
HAVING count(*) > 1
ORDER BY count(*) DESC, observation_datetime
LIMIT 20
"""

TOTALS = """
SELECT count(*) AS duplicate_groups,
       coalesce(sum(copies) - count(*), 0) AS rows_above_the_first,
       count(*) FILTER (WHERE distinct_values > 1) AS groups_that_disagree
FROM (
    SELECT count(*) AS copies, count(DISTINCT value) AS distinct_values
    FROM transducer_observation
    GROUP BY deployment_id, parameter_id, observation_datetime
    HAVING count(*) > 1
) g
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", required=True, help="PROJECT:REGION:INSTANCE")
    parser.add_argument("--database", required=True, help="e.g. ocotillo-staging")
    parser.add_argument("--user", help="IAM principal; defaults to your gcloud account")
    args = parser.parse_args()

    user = args.user or _current_account()
    if not user:
        print("Could not determine your gcloud account; pass --user.", file=sys.stderr)
        return 2

    from google.cloud.sql.connector import Connector

    connector = Connector()
    try:
        conn = connector.connect(
            args.instance,
            "pg8000",
            user=user,
            db=args.database,
            enable_iam_auth=True,
        )
    except Exception as exc:  # noqa: BLE001 - the message is the useful part
        print(f"Could not connect as {user}: {exc}", file=sys.stderr)
        print(
            "\nIf this is a permissions error, the principal probably has no "
            "database user:\n"
            f"  gcloud sql users create {user} --instance="
            f"{args.instance.split(':')[-1]} --type=cloud_iam_user",
            file=sys.stderr,
        )
        return 1

    try:
        cursor = conn.cursor()
        cursor.execute(TOTALS)
        groups, extra_rows, disagreeing = cursor.fetchone()

        print(f"Database: {args.database}")
        print(f"  duplicate groups     : {groups}")
        print(f"  rows above the first : {extra_rows}")
        print(f"  groups that disagree : {disagreeing}")

        if not groups:
            print("\nNo duplicates. The unique constraint migration is safe to run.")
            return 0

        print(
            "\nThe migration will FAIL until these are resolved.\n"
            "Groups that disagree are the ones to look at first: those rows hold "
            "different values for the same instant, so they are conflicting "
            "measurements rather than redundant copies, and collapsing them "
            "discards a reading somebody recorded."
        )
        cursor.execute(DUPLICATE_GROUPS)
        print("\n  deployment  parameter  observed                  copies  values")
        for dep, param, observed, copies, values in cursor.fetchall():
            print(
                f"  {dep:>10}  {param:>9}  {str(observed):<24}  {copies:>6}  {values:>6}"
            )
        return 1
    finally:
        conn.close()
        connector.close()


def _current_account() -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:  # noqa: BLE001
        return None
    account = result.stdout.strip()
    return account or None


if __name__ == "__main__":
    raise SystemExit(main())


# ============= EOF =============================================
