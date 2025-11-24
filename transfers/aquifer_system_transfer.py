import time
from sqlalchemy.orm import Session
from pydantic import ValidationError

from db import AquiferSystem
from schemas.aquifer_system import CreateAquiferSystem
from transfers.util import read_csv, replace_nans, logger


def transfer_aquifer_systems(session: Session, limit: int = None) -> tuple:
    """
    Transfer aquifer system data from LU_AquiferClass CSV to the database.

    This creates the master list of named aquifer systems (e.g., Ogallala Aquifer). the primary_type field is set
    to "Unknown" as a placeholder and will be updated during well transfer when we know what type each well encounters.

    This should be run BEFORE well_transfer.py so that aquifer records exist for wells to reference.

    Args:
        session (Session): SQLAlchemy database session
        limit (int, optional): Limit the number of records to transfer (for testing).

    Returns:
        tuple: (input_df, cleaned_df, errors)
    """
    # 1. Read the CSV file
    input_df = read_csv("LU_AquiferClass")

    # 2. Replace NaNs with NOne
    cleaned_df = replace_nans(input_df)

    # 3. Initialize tracking variables for logging
    n = len(input_df)
    step = 25
    start_time = time.time()
    errors = []
    created_count = 0
    skipped_count = 0

    logger.info(f"Starting transfer of {n} aquifer systems from LU_AquiferClass.")

    # 4. Process each row
    for i, row in enumerate(cleaned_df.itertuples()):
        # check if limit is reached
        if limit and i >= limit:
            logger.info(f"Reached limit of {limit} rows. Stopping migration.")
            break

        # Log progress every 'step' rows
        if i and not i % 25:
            logger.info(
                f"Processing row {i} of {n}. Avg rows per second: {step / (time.time() - start_time):.2f}"
            )
            start_time = time.time()

            # Commit progress periodically
            try:
                session.commit()
            except Exception as e:
                logger.critical(f"Error committing aquifer system {i}: {e}")
                session.rollback()
                continue

        # 5. Extract aquifer code and name
        aquifer_code = row.CODE
        aquifer_name = row.MEANING

        if not aquifer_name:
            logger.warning(
                f"Row {i} (code: {aquifer_code}) has no aquifer name (MEANING). Skipping."
            )
            skipped_count += 1
            continue

        # 6. Check if aquifer system already exists
        existing = (
            session.query(AquiferSystem)
            .filter(AquiferSystem.name == aquifer_name)
            .first()
        )

        if existing:
            logger.info(
                f"Aquifer '{aquifer_name}' (code: {aquifer_code}) already exists. Skipping."
            )
            skipped_count += 1
            continue

        # 7. Prepare data dictionary
        try:
            data = CreateAquiferSystem(
                name=aquifer_name,
                description=None,  # can be updated later
                primary_aquifer_type="Unknown",  # placeholder - will be updated during well transfer
            )

            # Validate data using Pydantic schema
            CreateAquiferSystem.model_validate(data)

        except ValidationError as e:
            errors.append({"code": aquifer_code, "name": aquifer_name, "error": str(e)})
            logger.critical(
                f"Error creating aquifer system '{aquifer_name}' (code: {aquifer_code}) (row {i}): {e}"
            )
            continue

        # 8. Create database record
        aquifer_system = None
        try:
            aquifer_data = data.model_dump()
            aquifer_system = AquiferSystem(**aquifer_data)
            session.add(aquifer_system)
            created_count += 1

            logger.info(
                f"Created aquifer system: {aquifer_system.name} (code: {aquifer_code})"
            )

        except Exception as e:
            if aquifer_system is not None:
                session.expunge(aquifer_system)
            errors.append({"code": aquifer_code, "name": aquifer_name, "error": str(e)})
            logger.critical(
                f"Error creating aquifer system record '{aquifer_name}': {e}"
            )
            continue

        # 9. Final commit
    try:
        session.commit()
        logger.info(
            f"Successfully transferred {created_count} aquifer systems, skipped {skipped_count}. "
            f"Note: primary_type set to 'Unknown' and will be updated during well transfer."
        )
    except Exception as e:
        logger.critical(f"Error in final commit: {e}")
        session.rollback()

    return input_df, cleaned_df, errors
