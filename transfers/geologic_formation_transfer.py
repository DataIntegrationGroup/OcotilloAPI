import time
from sqlalchemy.orm import Session
from pydantic import ValidationError

from db import GeologicFormation
from schemas.geologic_formation import CreateGeologicFormation
from transfers.util import read_csv, replace_nans, logger


def transfer_geologic_formations(session: Session, limit: int = None) -> tuple:
    """
    Transfer geologic formation data from LU_GeologicFormation CSV to the database.

    This should be run BEFORE well_transfer.py so that geologic formation records exist for wells to reference.

    Args:
        session (Session): SQLAlchemy database session
        limit (int, optional): Optional limit on number of records to transfer (for testing).

    Returns:
        tuple: (input_df, cleaned_df, errors)
    """
    # 1. Read the CSV file
    input_df = read_csv("LU_Formations")

    # 2. Replace NaNs with None
    cleaned_df = replace_nans(input_df)

    # 3. Initialize tracking variables for logging
    n = len(cleaned_df)
    step = 25
    start_time = time.time()
    errors = []
    created_count = 0
    skipped_count = 0

    logger.info(f"Starting transfer of {n} geologic formations")

    # 4. Process each row
    for i, row in enumerate(cleaned_df.itertuples()):
        # check if limit is reached
        if limit and i >= limit:
            logger.info(f"Reached limit of {limit} rows. Stopping migration.")
            break

        # Log progress every 'step' rows
        if i and not i % step:
            logger.info(
                f"Processing row {i} of {n}. Avg rows per second: {step / (time.time() - start_time):.2f}"
            )
            start_time = time.time()

            # Commit progress periodically
            try:
                session.commit()
            except Exception as e:
                logger.critical(f"Error committing geologic formations: {e}")
                session.rollback()
                continue

        # 5. Extract formation code and description
        formation_code = row.Code

        if not formation_code:
            logger.warning(f"Skipping row {i}: Missing formation code")
            skipped_count += 1
            continue

        # Check if this formation already exists
        existing = (
            session.query(GeologicFormation)
            .filter(GeologicFormation.formation_code == formation_code)
            .first()
        )

        if existing:
            logger.info(
                f"Skipping row {i}: Formation code {formation_code} already exists"
            )
            skipped_count += 1
            continue

        # 6. Prepare data for creation
        # Note: We only store the formation_code. Formation names will be mapped by the API using a
        # formations.json file from authoritative sources (e.g., USGS).
        # The description field is left as None and can be populated later if needed.
        # Note: lithology is set to None here and will be updated during stratigraphy transfer
        try:
            data = CreateGeologicFormation(
                formation_code=formation_code,
                description=None,  # Not storing from legacy data
                lithology=None,  # Will be populated from Stratigraphy.csv
            )

            # Validate the data using Pydantic schema
            CreateGeologicFormation.model_validate(data)

        except ValidationError as e:
            errors.append({"code": formation_code, "errors": e.errors()})
            logger.critical(
                f"Validation error for row {i} with Code {formation_code}: {e.errors()}"
            )
            continue
        except Exception as e:
            errors.append({"code": formation_code, "errors": str(e)})
            logger.critical(f"Error preparing data for {formation_code}: {e}")
            continue

        # 7. Create database object
        geologic_formation = None
        try:
            formation_data = data.model_dump()
            geologic_formation = GeologicFormation(**formation_data)
            session.add(geologic_formation)
            created_count += 1

            logger.info(
                f"Created geologic formation: {geologic_formation.formation_code}"
            )

        except Exception as e:
            if geologic_formation is not None:
                session.expunge(geologic_formation)
            errors.append({"code": formation_code, "error": str(e)})
            logger.critical(
                f"Error creating geologic formation for {formation_code}: {e}"
            )
            continue

    # 8. Final commit
    try:
        session.commit()
        logger.info(
            f"Successfully transferred {created_count} geologic formations, skipped {skipped_count}. "
            f"Note: lithology is None and will be updated during stratigraphy transfer."
        )
    except Exception as e:
        logger.critical(f"Error during final commit of geologic formations: {e}")
        session.rollback()

    return input_df, cleaned_df, errors
