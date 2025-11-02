from db.thing import Thing
from db.engine import session_ctx


def seed():
    """Create a single contact, location, and water well."""
    with session_ctx() as session:
        # Create a water well
        water_well = Thing(
            name="TEST-0001",
            thing_type="water well",
            release_status="draft",
            first_visit_date="2023-03-03",
            well_depth=100.0,
            hole_depth=100.0,
            well_construction_notes="Seed well construction notes",
            well_casing_diameter=5.0,
            well_casing_depth=10.0,
        )
        session.add(water_well)
        session.commit()
        session.refresh(water_well)
        print(f"Created water well: {water_well.id} - {water_well.name}")


if __name__ == "__main__":
    seed()

# ============= EOF =============================================
