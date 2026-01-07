"""
Transfer script for stratigraphy (lithology log) data.

This creates ThingGeologicFormationAssociation records from the Stratigraphy CSV, which contains depth-specific
formation information for wells. It also updates the GeologicFormation.lithology field based on the
Stratigraphy.Lithology data.
"""

import time

from sqlalchemy.orm import Session

from db import Thing, GeologicFormation, ThingGeologicFormationAssociation
from transfers.util import (
    read_csv,
    replace_nans,
    filter_to_valid_point_ids,
    lexicon_mapper,
    logger,
)


def transfer_stratigraphy(session: Session, limit: int = None) -> tuple:
    """
    Transfer detailed stratigraphy (lithology log) data from Stratigraphy CSV.

    The Stratigraphy CSV contains multiple rows per well, each representing a
    depth interval, the formation encountered, and its lithology.

    Fields used:
        - PointID: Links to the well
        - UnitIdentifier: Formation code (maps to LU_Formations)
        - StratTop: Top depth of the layer (feet below ground surface)
        - StratBottom: Bottom depth of the layer (feet below ground surface)
        - Lithology: Lithology code (maps to LU_Lithology via ABBREVIATION field)

    This should be run AFTER:
        1. transfer_geologic_formations.py (so formations exist)
        2. transfer_wells.py (so wells exist)

    Args:
        session: Database session
        limit: Optional limit on number of WELLS to process (for testing)

    Returns:
        tuple: (input_df, cleaned_df, errors)
    """
    # 1. Read and clean data
    input_df = read_csv("Stratigraphy")
    cleaned_df = replace_nans(input_df)

    # Step 2: Filter to only wells that exist in database
    cleaned_df = filter_to_valid_point_ids(cleaned_df)

    n_records = len(cleaned_df)
    n_wells = len(cleaned_df["PointID"].unique())

    logger.info(
        f"Starting transfer of {n_records} stratigraphy records for {n_wells} wells"
    )

    # 3. Initialize tracking variables for logging
    step = 25
    start_time = time.time()
    errors = []
    created_count = 0
    skipped_count = 0
    lithology_updates = 0

    # Step 4: Group by well for efficient processing
    well_groups = cleaned_df.groupby("PointID")

    formations = session.query(GeologicFormation).all()
    things = session.query(Thing).all()

    formations = {f.formation_code: f for f in formations}
    things = {t.name: t for t in things}

    for well_index, (pointid, strat_group) in enumerate(well_groups):
        # Check limit (on number of wells, not records)
        if limit is not None and limit > 0 and well_index >= limit:
            logger.info(f"Reached limit of {limit} wells. Stopping.")
            break

        # Progress logging every 25 wells
        if well_index and not well_index % step:
            logger.info(
                f"Processing well {well_index} of {n_wells}, "
                f"avg wells per second: {step / (time.time() - start_time):.2f}"
            )
            start_time = time.time()

            # Periodic commit
            try:
                session.commit()
            except Exception as e:
                logger.critical(f"Error committing stratigraphy records: {e}")
                session.rollback()
                continue

        # 5. Get the well from database
        thing = things.get(pointid)
        if not thing:
            logger.warning(
                f"Well {pointid} not found in database, skipping stratigraphy"
            )
            skipped_count += len(strat_group)
            continue

        logger.info(
            f"Processing {len(strat_group)} stratigraphy layers for well {pointid}"
        )

        # 6. Process each stratigraphy record for this well
        for layer_index, row in enumerate(strat_group.itertuples()):
            # Validate required fields
            # UnitIdentifier
            if not hasattr(row, "UnitIdentifier") or not row.UnitIdentifier:
                logger.critical(
                    f"Stratigraphy record {layer_index} for {pointid} has no UnitIdentifier, skipping"
                )
                skipped_count += 1
                errors.append(
                    {
                        "pointid": pointid,
                        "layer": layer_index,
                        "error": "Missing UnitIdentifier",
                    }
                )
                continue
            # StratTop
            if not hasattr(row, "StratTop") or row.StratTop is None:
                logger.critical(
                    f"Stratigraphy record {layer_index} for {pointid} has no StratTop, skipping"
                )
                skipped_count += 1
                errors.append(
                    {
                        "pointid": pointid,
                        "layer": layer_index,
                        "error": "Missing StratTop",
                    }
                )
                continue
            # StratBottom
            if not hasattr(row, "StratBottom") or row.StratBottom is None:
                logger.critical(
                    f"Stratigraphy record {layer_index} for {pointid} has no StratBottom, skipping"
                )
                skipped_count += 1
                errors.append(
                    {
                        "pointid": pointid,
                        "layer": layer_index,
                        "error": "Missing StratBottom",
                    }
                )
                continue

            # Extract formation code
            formation_code = row.UnitIdentifier.strip()

            # Validate depth values
            try:
                top_depth = float(row.StratTop)
                bottom_depth = float(row.StratBottom)
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid depth values: StratTop={row.StratTop}, StratBottom={row.StratBottom}"
                logger.critical(
                    f"{pointid} layer {layer_index}: {error_msg}, error: {e}"
                )
                errors.append(
                    {
                        "pointid": pointid,
                        "layer": layer_index,
                        "error": error_msg,
                        "details": str(e),  # for conversion errors
                    }
                )
                skipped_count += 1
                continue

            # Validate depth logic
            if top_depth >= bottom_depth:
                error_msg = (
                    f"Invalid depth logic: top={top_depth} >= bottom={bottom_depth}"
                )
                logger.critical(f"{pointid} layer {layer_index}: {error_msg}")
                errors.append(
                    {"pointid": pointid, "layer": layer_index, "error": error_msg}
                )
                skipped_count += 1
                continue

            if top_depth < 0:
                error_msg = f"Negative top depth: {top_depth}"
                logger.critical(f"{pointid} layer {layer_index}: {error_msg}")
                errors.append(
                    {"pointid": pointid, "layer": layer_index, "error": error_msg}
                )
                skipped_count += 1
                continue

            # 7. Get or create the formation
            # formation = (
            #     session.query(GeologicFormation)
            #     .filter(GeologicFormation.formation_code == formation_code)
            #     .first()
            # )

            formation = formations.get(formation_code)
            if not formation:
                logger.info(f"Geologic formation not in lexicon: {formation_code}")
                skipped_count += 1
                continue

                # Create new formation if it doesn't exist
                logger.info(f"Creating new geologic formation: {formation_code}")
                formation = GeologicFormation(
                    formation_code=formation_code,
                    description=None,
                    lithology=None,  # Will be set below
                )
                session.add(formation)
                session.flush()

            # 8. Update formation lithology if available and not already set
            if hasattr(row, "Lithology") and row.Lithology:
                try:
                    # Map lithology code to geologic_formation.lithology using ABBREVIATION field
                    lithology = lexicon_mapper.map_value(
                        f"LU_Lithology:{row.Lithology}"
                    )

                    # Update if formation does not have lithology yet
                    if not formation.lithology:
                        formation.lithology = lithology
                        lithology_updates += 1
                        logger.info(f"Set lithology for {formation_code}: {lithology}")
                    elif formation.lithology != lithology:
                        # Log if there's a mismatch (different lithology for same formation)
                        logger.warning(
                            f"Formation {formation_code} has conflicting lithology: "
                            f"existing='{formation.lithology}', new='{lithology}'."
                        )
                except KeyError:
                    logger.warning(
                        f"Unknown lithology code '{row.Lithology}' for {pointid}, skipping lithology update"
                    )
                except Exception as e:
                    logger.warning(f"Error mapping lithology '{row.Lithology}': {e}")

            # 9. Create ThingGeologicFormationAssociation record
            try:
                formation_assoc = ThingGeologicFormationAssociation(
                    thing=thing,
                    geologic_formation=formation,
                    top_depth=top_depth,
                    bottom_depth=bottom_depth,
                )
                session.add(formation_assoc)
                created_count += 1

                logger.info(
                    f"  Layer {layer_index + 1}: {formation.formation_code} "
                    f"from {top_depth:.1f} to {bottom_depth:.1f} ft"
                )

            except Exception as e:
                logger.critical(
                    f"Error creating stratigraphy association for {pointid}, "
                    f"formation {formation_code}: {e}"
                )
                errors.append(
                    {
                        "pointid": pointid,
                        "formation": formation_code,
                        "layer": layer_index,
                        "error": str(e),
                    }
                )
                skipped_count += 1
                continue

    # 10. Final commit
    try:
        session.commit()
        logger.info(
            f"Successfully transferred stratigraphy: "
            f"{created_count} associations created, {skipped_count} skipped, "
            f"{lithology_updates} lithology fields updated, {len(errors)} errors"
        )
    except Exception as e:
        logger.critical(f"Error in final commit: {e}")
        session.rollback()

    return input_df, cleaned_df, errors
