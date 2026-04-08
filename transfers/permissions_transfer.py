from datetime import datetime


from pandas import isna
from sqlalchemy.orm import Session

from db import Thing, PermissionHistory, Contact, ThingContactAssociation
from transfers.util import read_csv, logger, replace_nans, chunk_by_size
from transfers.transferer import Transferer

"""
Developer's notes

According to Laila the column WellData.OpenWellLoggerOK only pertains to the
physical properties of a well (that is, if a datalogger can be installed). It
does not pertain to permissions.
"""


def _make_permission(
    wdf, well, contact_id, nma_field, permission_type
) -> PermissionHistory | None:

    values = wdf.loc[wdf["PointID"] == well.name, nma_field].values
    if len(values) == 0:
        return None
    elif isna(values[0]):
        return None

    permission_allowed = bool(values[0])
    permission = PermissionHistory(
        contact_id=contact_id,
        permission_type=permission_type,
        permission_allowed=permission_allowed,
        start_date=datetime.today().date(),
        target_id=well.id,
        target_table="thing",
    )

    logger.info(
        f"Transferred {permission_type} permission for well {well.name}: {permission_allowed}."
    )

    return permission


def transfer_permissions(session: Session, pointids: list[str] | None = None) -> None:
    """
    The transferred wells and contacts need to be transferred first
    - to access the auto-generated well IDs
    - to know who gave permission to which well since contact_id is required for
        PermissionHistory
    """
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    wdf = replace_nans(wdf)
    if pointids:
        normalized_pointids = wdf["PointID"].map(Transferer._normalize_pointid)
        wdf = wdf[normalized_pointids.isin(set(pointids))]

    logger.info("Starting transfer: Permissions")
    transferred_wells_query = (
        session.query(Thing, Contact)
        .select_from(Thing)
        .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
        .join(Contact, Contact.id == ThingContactAssociation.contact_id)
        .filter(Thing.thing_type == "water well")
        .order_by(Thing.name)
    )
    if pointids:
        transferred_wells_query = transferred_wells_query.filter(
            Thing.name.in_(pointids)
        )
    transferred_wells = transferred_wells_query.all()
    existing_permissions = {
        (target_id, contact_id, permission_type)
        for target_id, contact_id, permission_type in session.query(
            PermissionHistory.target_id,
            PermissionHistory.contact_id,
            PermissionHistory.permission_type,
        )
        .filter(PermissionHistory.target_table == "thing")
        .all()
    }
    created_count = 0
    visited = []
    for chunk in chunk_by_size(transferred_wells, 100):
        objs = []
        for row in chunk.itertuples():
            well = row.Thing
            contact = row.Contact
            if well.id in visited:
                continue

            visited.append(well.id)

            permission = _make_permission(
                wdf, well, contact.id, "SampleOK", "Water Chemistry Sample"
            )
            if (
                permission
                and (
                    well.id,
                    contact.id,
                    permission.permission_type,
                )
                not in existing_permissions
            ):
                objs.append(permission)
                created_count += 1
                existing_permissions.add(
                    (well.id, contact.id, permission.permission_type)
                )

            permission = _make_permission(
                wdf, well, contact.id, "MonitorOK", "Water Level Sample"
            )
            if (
                permission
                and (
                    well.id,
                    contact.id,
                    permission.permission_type,
                )
                not in existing_permissions
            ):
                objs.append(permission)
                created_count += 1
                existing_permissions.add(
                    (well.id, contact.id, permission.permission_type)
                )

        session.bulk_save_objects(objs)
        session.commit()

    logger.info("Completed transfer: Permissions (%s records)", created_count)
