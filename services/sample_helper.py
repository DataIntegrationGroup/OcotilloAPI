from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import Sample, Thing, FieldEvent, FieldActivity
from services.query_helper import order_sort_filter


def get_samples(
    session: Session,
    order: str | None = None,
    sort: str | None = None,
    filter_: str | None = None,
):
    query = select(Sample, Thing, FieldEvent)
    query = query.join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
    query = query.join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
    query = query.join(Thing, FieldEvent.thing_id == Thing.id)

    query = order_sort_filter(query, Sample, sort, order, filter_)

    return paginate(query, conn=session)


def get_sample_by_id(session: Session, sample_id: int) -> Sample | None:
    query = select(Sample).where(Sample.id == sample_id)
    return session.execute(query).scalar_one_or_none()
