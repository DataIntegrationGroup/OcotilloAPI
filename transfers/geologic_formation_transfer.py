from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

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

    if limit is not None:
        cleaned_df = cleaned_df.head(limit)

    # 3. Initialize tracking variables for logging
    n = len(cleaned_df)
    errors = []
    prepared_count = 0
    skipped_count = 0

    logger.info(
        "Starting transfer: GeologicFormations (%s rows) from LU_Formations",
        n,
    )

    # 4. Build a deduplicated, validated payload for a set-based insert.
    rows_to_insert: list[dict] = []
    seen_codes: set[str] = set()
    for i, row in enumerate(cleaned_df.itertuples(index=False), start=1):
        if i % 1000 == 0:
            logger.info("Prepared %s/%s geologic formation rows", i, n)

        # 5. Extract and normalize formation code
        formation_code = getattr(row, "Code", None)

        if not formation_code:
            logger.warning("Skipping row %s: Missing formation code", i)
            skipped_count += 1
            continue

        formation_code = str(formation_code).strip().upper()
        if not formation_code:
            logger.warning("Skipping row %s: Blank formation code", i)
            skipped_count += 1
            continue

        if formation_code in seen_codes:
            # Duplicate code in source payload; keep first one only.
            skipped_count += 1
            continue
        seen_codes.add(formation_code)

        # 6. Validate and prepare payload
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
            skipped_count += 1
            errors.append({"code": formation_code, "errors": e.errors()})
            logger.critical(f"Validation error for row {i} with Code {formation_code}")
            continue
        except Exception as e:
            skipped_count += 1
            errors.append({"code": formation_code, "errors": str(e)})
            logger.critical(f"Error preparing data for {formation_code}: {e}")
            continue

        rows_to_insert.append(data.model_dump())
        prepared_count += 1

    # 7. Bulk insert with idempotent upsert semantics.
    created_count = 0
    try:
        if rows_to_insert:
            stmt = (
                pg_insert(GeologicFormation)
                .values(rows_to_insert)
                .on_conflict_do_nothing(index_elements=["formation_code"])
                .returning(GeologicFormation.formation_code)
            )
            inserted_codes = session.execute(stmt).scalars().all()
            created_count = len(inserted_codes)

        session.commit()
        logger.info(
            "Successfully transferred geologic formations. prepared=%s created=%s skipped=%s "
            "existing_or_duplicate=%s. Note: lithology is None and will be updated during stratigraphy transfer.",
            prepared_count,
            created_count,
            skipped_count,
            max(prepared_count - created_count, 0),
        )
    except Exception as e:
        logger.critical(f"Error during final commit of geologic formations: {e}")
        session.rollback()

    logger.info("Completed transfer: GeologicFormations")
    return input_df, cleaned_df, errors
