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
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import Thing, Group
from db.engine import session_ctx
from transfers.util import read_csv


def transfer_groups(
    session: Session,
) -> None:
    wdf = read_csv("projects.csv")
    for i, row in enumerate(wdf.itertuples()):

        sql = select(Group).where(Group.name == row.Project)
        group = session.scalars(sql).one_or_none()
        if not group:
            # add a group for each project
            group = Group(name=row.Project)

        for prefix in row.PointIDPrefix.split(","):
            prefix = prefix.strip()
            if prefix:
                # get all PointIDs that start with prefix
                sql = select(Thing).where(Thing.name.like(f"{prefix}%"))
                records = session.scalars(sql).all()
                if records:
                    print(f"Adding {len(records)} things to group {group.name}, prefix {prefix}")
                    group.things = records

        session.add(group)
        session.commit()


if __name__ == "__main__":
    with session_ctx() as session:
        transfer_groups(session)
# ============= EOF =============================================
