from sqlalchemy.orm import Session, joinedload
from fastapi_pagination.ext.sqlalchemy import paginate

from db import FieldEvent, FieldActivity, Sample
from services.query_helper import order_sort_filter


def get_db_samples(
    session: Session,
    order: str | None = None,
    sort: str | None = None,
    filter_: str | None = None,
):
    query = session.query(Sample).options(
        # Eagerly load related FieldActivity and FieldEvent to avoid N+1 problem
        joinedload(Sample.field_activity)
        .joinedload(FieldActivity.field_event)
        .joinedload(FieldEvent.thing)
    )

    query = order_sort_filter(query, Sample, sort, order, filter_)

    return paginate(query)
