from sqlalchemy import inspect

from db.engine import engine


def test_asset_table_has_publish_tracking_columns():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("asset")}

    required_columns = [
        "publish_target",
        "publish_status",
        "publish_workspace",
        "publish_store_name",
        "publish_layer_name",
        "publish_last_attempt_at",
        "publish_last_error",
    ]

    missing = [column for column in required_columns if column not in columns]
    assert not missing, f"Asset table missing publish columns: {missing}"
