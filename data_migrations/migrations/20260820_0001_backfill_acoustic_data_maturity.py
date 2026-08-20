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
Set `data_maturity` on the acoustic (Wellntel) transducer observations that
alembic revision `b2c3d4e5f6a7` left NULL.

That revision backfilled maturity from `nma_waterlevelscontinuous_pressure_qced`,
the AMPAPI flag recording whether a reading was quality controlled. Acoustic
readings have no such flag -- AMPAPI's `WaterLevelsContinuous_Acoustic` table has
no `QCed` column at all -- so all 394,086 of them were skipped, which is the
entire acoustic record (BDMS-1169).

`MATURITY` is a deliberate choice, not a derivation. There is no QC field in the
acoustic legacy schema to read, so nothing here computes the answer; the value
below is the one recorded for these readings, applied uniformly. The transfer's
`review_status='approved'` blocks are *not* evidence for it -- those come from
`PublicRelease`, which every acoustic source row carries and which describes
visibility rather than review.

Rows are matched on `nma_waterlevelscontinuous_acoustic_global_id`, the AMPAPI
row identity. It is written by `WaterLevelsContinuousAcousticTransferer` on every
acoustic row and never by the pressure transferer, so it is the provenance
marker: 394,086 rows carry it, and they are exactly the rows with no
`pressure_qced`.

Only rows where `data_maturity` is already NULL are touched. Re-running is
therefore a no-op, and a maturity set deliberately since -- by the hydrograph
corrector, or by a later migration once the acoustic QC history is known -- is
left alone rather than reset to the blanket value.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.transducer import TransducerObservation

MATURITY = "approved"


def run(session: Session) -> None:
    """Set the maturity on acoustic observations that have none."""
    result = session.execute(
        update(TransducerObservation)
        .where(
            TransducerObservation.nma_waterlevelscontinuous_acoustic_global_id.isnot(
                None
            ),
            TransducerObservation.data_maturity.is_(None),
        )
        .values(data_maturity=MATURITY)
        .execution_options(synchronize_session=False)
    )
    print(
        f"  set data_maturity={MATURITY!r} on {result.rowcount} acoustic observations"
    )
    return None


MIGRATION = DataMigration(
    id="20260820_0001_backfill_acoustic_data_maturity",
    alembic_revision="b2c3d4e5f6a7",
    name="Backfill data_maturity on acoustic (Wellntel) observations",
    description=(
        "Revision b2c3d4e5f6a7 backfilled data_maturity from the pressure QC "
        "flag, which acoustic readings do not have, leaving the entire 394,086 "
        f"row Wellntel record NULL (BDMS-1169). Sets it to {MATURITY!r}. Only "
        "touches rows whose maturity is still NULL."
    ),
    run=run,
    is_repeatable=False,
)


# ============= EOF =============================================
