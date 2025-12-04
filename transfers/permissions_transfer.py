from sqlalchemy.orm import Session
from datetime import datetime

from db import Thing, PermissionHistory, Contact, ThingContactAssociation
from transfers.util import read_csv, logger, replace_nans, chunk_by_size

"""
Developer's notes

According to Laila the column WellData.OpenWellLoggerOK only pertains to the
physical properties of a well (that is, if a datalogger can be installed). It
does not pertain to permissions.
"""


def make_water_level_sample_permission(wdf, well, contact_id):
    allow_water_level_samples = wdf.loc[wdf["PointID"] == well.name, "MonitorOK"].values

    # try:
    permission_allowed = bool(allow_water_level_samples[0])
    permission = PermissionHistory(
        contact_id=contact_id,
        permission_type="Water Level Sample",
        permission_allowed=permission_allowed,
        start_date=datetime.today().date(),
        target_id=well.id,
        target_table="thing",
    )
    logger.info(
        f"Transferred Water Level Sample permission for well {well.name}: {permission_allowed}."
    )
    return permission


def make_chemistry_permission(wdf, well, contact_id):
    allow_water_chemistry_samples = wdf.loc[
        wdf["PointID"] == well.name, "SampleOK"
    ].values

    permission_allowed = bool(allow_water_chemistry_samples[0])
    permission = PermissionHistory(
        contact_id=contact_id,
        permission_type="Water Chemistry Sample",
        permission_allowed=permission_allowed,
        start_date=datetime.today().date(),
        target_id=well.id,
        target_table="thing",
    )
    return permission


def transfer_permissions(session: Session):
    """
    The transferred wells and contacts need to be transferred first
    - to access the auto-generated well IDs
    - to know who gave permission to which well since contact_id is required for
        PermissionHistory
    """
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    wdf = replace_nans(wdf)

    transferred_wells = (
        session.query(Thing, Contact)
        .select_from(Thing)
        .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
        .join(Contact, Contact.id == ThingContactAssociation.contact_id)
        .filter(Thing.thing_type == "water well")
        .order_by(Thing.name)
        .all()
    )
    visited = []
    for chunk in chunk_by_size(transferred_wells, 100):
        objs = []
        for row in chunk.itertuples():
            well = row.Thing
            contact = row.Contact
            if well.id in visited:
                continue

            visited.append(well.id)

            permission = make_chemistry_permission(wdf, well, contact.id)
            objs.append(permission)

            permission = make_water_level_sample_permission(wdf, well, contact.id)
            objs.append(permission)

        session.bulk_save_objects(objs)
