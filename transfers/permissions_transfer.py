from sqlalchemy.orm import Session
from datetime import datetime

from db import Thing, PermissionHistory
from transfers.util import read_csv, logger, replace_nans


def transfer_permissions(session: Session):
    """
    The transferred wells and contacts need to be queried to know who gave
    permission to which well since contact_id is required for PermissionHistory
    """
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    wdf = replace_nans(wdf)

    transferred_wells = (
        session.query(Thing).filter(Thing.thing_type == "water well").all()
    )

    for well in transferred_wells:
        if len(well.contacts) == 0:
            logger.critical(
                f"Well {well.name} has no associated contacts; skipping permission transfer."
            )
            continue
        else:
            # Assuming the first contact is the relevant one
            contact_id = well.contacts[0].id

        allow_water_level_samples = wdf.loc[
            wdf["PointID"] == well.name, "MonitorOK"
        ].values
        if len(allow_water_level_samples) > 0 and allow_water_level_samples is not None:
            try:
                permission_allowed = bool(allow_water_level_samples[0])
                permission = PermissionHistory(
                    contact_id=contact_id,
                    permission_type="Water Level Sample",
                    permission_allowed=permission_allowed,
                    start_date=datetime.today().date(),
                    target_id=well.id,
                    target_table="thing",
                )
                session.add(permission)
                logger.info(
                    f"Transferred Water Level Sample permission for well {well.name}: {permission_allowed}."
                )
            except Exception as e:
                logger.error(f"Error transferring permission for well {well.name}: {e}")
                session.rollback()
                pass

        allow_water_chemistry_samples = wdf.loc[
            wdf["PointID"] == well.name, "SampleOK"
        ].values
        if (
            len(allow_water_chemistry_samples) > 0
            and allow_water_chemistry_samples is not None
        ):
            try:
                permission_allowed = bool(allow_water_chemistry_samples[0])
                permission = PermissionHistory(
                    contact_id=contact_id,
                    permission_type="Water Chemistry Sample",
                    permission_allowed=permission_allowed,
                    start_date=datetime.today().date(),
                    target_id=well.id,
                    target_table="thing",
                )
                session.add(permission)
                logger.info(
                    f"Transferred Water Chemistry Sample permission for well {well.name}: {permission_allowed}."
                )
            except Exception as e:
                logger.error(f"Error transferring permission for well {well.name}: {e}")
                session.rollback()
                pass

        allow_datalogger_installation = wdf.loc[
            wdf["PointID"] == well.name, "OpenWellLoggerOK"
        ].values
        if (
            len(allow_datalogger_installation) > 0
            and allow_datalogger_installation is not None
        ):
            try:
                permission_allowed = bool(allow_datalogger_installation[0])
                permission = PermissionHistory(
                    contact_id=contact_id,
                    permission_type="Datalogger Installation",
                    permission_allowed=permission_allowed,
                    start_date=datetime.today().date(),
                    target_id=well.id,
                    target_table="thing",
                )
                session.add(permission)
                logger.info(
                    f"Transferred Datalogger Installation permission for well {well.name}: {permission_allowed}."
                )
            except Exception as e:
                logger.error(f"Error transferring permission for well {well.name}: {e}")
                session.rollback()
                pass

    session.commit()
