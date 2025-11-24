import time
from sqlalchemy.orm import Session
from pydantic import ValidationError

from db import GeologicFormation
from schemas.geologic_formation import CreateGeologicFormation
from transfers.util import read_csv, replace_nans, lexicon_mapper, logger


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
    input_df = read_csv("LU_Formation")

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
                logger.critical(f"Error committing geologic formation {i}: {e}")
                session.rollback()
                continue

        try:
            payload = CreateGeologicFormation(
                name=row.GeologicFormationName,
                description=row.Description,
                lithology=lexicon_mapper("Lithology", row.Lithology),
                age=lexicon_mapper("GeologicAge", row.Age),
            )
            formation = GeologicFormation(**payload.dict())
            session.add(formation)
            created_count += 1
        except ValidationError as e:
            error_msg = f"Validation error for row {i} with GeologicFormationName {row.GeologicFormationName}: {e.errors()}"
            logger.critical(error_msg)
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error creating geologic formation for {row.GeologicFormationName}: {e}"
            logger.critical(error_msg)
            errors.append(error_msg)
            continue

    # Final commit after all rows are processed
    try:
        session.commit()
    except Exception as e:
        logger.critical(f"Error during final commit of geologic formations: {e}")
