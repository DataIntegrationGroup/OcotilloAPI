# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
import json
from typing import Any

from fastapi import HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import (
    Column,
    Float,
    Integer,
    Select,
    String,
    Text,
    and_,
    case,
    exists,
    func,
    not_,
    nulls_last,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.elements import OperatorExpression
from starlette.status import HTTP_404_NOT_FOUND

from db import search as search_func
from services.env import to_bool
from services.regex import QUERY_REGEX

# -----------------------------------------------------------------------------
# REFINE LIST FILTERS (JSON OVER QUERY STRING)
#
# Ocotillo UI uses Refine. ``getList`` sends each active DataGrid filter as one
# HTTP query parameter named ``filter``, repeated when multiple columns are
# filtered:
#
#   GET /contact?filter={"field":"things","operator":"contains","value":"DE"}
#
# FastAPI should declare that parameter as ``list[str]`` (alias ``filter``),
# never a single ``str``. A single-string binding drops extra filters when users
# combine column filters (wrong totals vs rows).
#
# Each JSON object must contain keys ``field``, ``operator``, and ``value``.
# ``order_sort_filter`` merges legacy ``filter_`` with ``filters``, JSON-decodes
# each string, then ANDs predicates by calling ``_apply_json_filter_clause``
# repeatedly.
#
# WHY VIRTUAL ``field`` NAMES (NOT RAW ORM NAMES FOR FILTERING)
#
# Some UI columns summarize **many related rows**, for example Associated Sites
# on contacts. SQLAlchemy exposes that as ``Contact.things``, an association
# proxy, **not** a ``String`` column. The default filter path does
# ``getattr(table, field)`` and applies ``ILIKE`` to a column. Proxies are not
# columns, and even if they were, "contains" must mean "match **any** linked
# site name", which needs a subquery or join. So we reserve virtual ``field``
# strings that match what the UI sends and implement them explicitly below.
#
# ASSOCIATION PAIR (INVERSE OF EACH OTHER)
#
# ``Thing`` virtual field ``contacts``: filter wells by **any** linked
# ``Contact.name`` via ``ThingContactAssociation``. Used from the wells list.
#
# ``Contact`` virtual field ``things``: filter contacts by **any** linked
# ``Thing.name`` via the same association table. Used from the contacts list.
#
# Both use ``EXISTS (SELECT 1 FROM … WHERE …)`` so we never duplicate parent
# rows when a contact links to many sites or a site has many contacts. Joining
# associations in the outer FROM would multiply rows and break pagination.
#
# Text predicates apply only to **name** on the far side of the association
# (not organization, role, or other columns) unless we deliberately extend the
# helpers and document that contract.
#
# Thing-only virtual fields ``monitoring_status`` / ``well_status``: latest
# open ``StatusHistory`` row for that type. Operators: contains, ncontains,
# startswith, endswith, eq, ne.
#
# All other ``field`` values must resolve to a real mapped SQL column on the
# primary table for this query (Thing or Contact).
#
# ``sort`` + ``order``: use mapped columns, or Thing keys in
# ``THING_VIRTUAL_SORT_FIELDS`` / Contact ``things``, implemented in
# ``_apply_thing_virtual_sort`` and ``_apply_contact_virtual_sort``.
# Python ``@property`` and association proxies are not valid ``ORDER BY`` targets.
#
# Long-form narrative: docs/refine-json-filters-and-virtual-fields.md
# -----------------------------------------------------------------------------


def make_where(col: Column, op: str, v: str) -> OperatorExpression:

    if op == "like":
        return col.like(v)
    elif op == "between":
        return col.between(*map(float, v.strip("[]").split(",")))
    else:

        def cast_value(col, val):
            if isinstance(col.type, Float):
                val = float(val)
            elif isinstance(col.type, Integer):
                val = int(val)
            return val

        return getattr(col, f"__{op}__")(cast_value(col, v))


def make_query(table: DeclarativeBase, query: str) -> OperatorExpression:
    # ensure the length of the query is reasonable
    if len(query) > 1000:
        raise ValueError("Query is too long")

    match = QUERY_REGEX.match(query)
    column = match.group("field")
    value = match.group("value")
    operator = match.group("operator")

    if value.startswith("'") and value.endswith("'"):
        value = value[1:-1]

    # Convert boolean strings to actual booleans
    value = to_bool(value)

    if "." in column:
        # Handle nested attributes
        column_parts = column.split(".")
        rel = getattr(table, column_parts[0])
        related_model = rel.property.mapper.class_
        related_column = getattr(related_model, column_parts[1])
        w = make_where(related_column, operator, value)
        w = rel.any(w)
    else:
        column = getattr(table, column)
        w = make_where(column, operator, value)

    return w


def simple_get_by_name(session, table, name) -> object | None:
    """
    Helper function to get a record by name from the database.
    """
    sql = select(table).where(table.name == name)
    result = session.execute(sql)
    return result.scalar_one_or_none()


def simple_get_by_id(
    session: Session, table: DeclarativeBase, item_id: int
) -> object | None:
    """
    Helper function to get a record by ID from the database.
    """

    item = session.get(table, item_id)
    if item is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"{table.__name__} with ID {item_id} not found.",
        )
    return item


def simple_all_getter(session, table) -> list[object]:
    """
    Helper function to get records from the database.
    """
    sql = select(table)
    return session.scalars(sql).all()


def _python_type(column: Any):
    try:
        return column.type.python_type
    except Exception:
        return None


def _apply_thing_derived_status_filter(
    sql: Select[Any],
    thing_table: type,
    status_type_literal: str,
    operator: str,
    value: Any,
) -> Select[Any]:
    """Filter Thing rows using the latest open StatusHistory row.

    Mirrors monitoring_status / well_status: open row (end_date None) with
    newest start_date wins.
    """
    from db.status_history import StatusHistory

    sh = StatusHistory
    tt = thing_table.__tablename__

    max_start = (
        select(func.max(sh.start_date))
        .select_from(sh)
        .where(
            sh.target_table == tt,
            sh.target_id == thing_table.id,
            sh.status_type == status_type_literal,
            sh.end_date.is_(None),
        )
        .correlate(thing_table)
        .scalar_subquery()
    )

    base_clause = and_(
        sh.target_table == tt,
        sh.target_id == thing_table.id,
        sh.status_type == status_type_literal,
        sh.end_date.is_(None),
        sh.start_date == max_start,
    )

    if operator == "ncontains":
        return sql.where(
            ~exists(
                select(1).where(
                    base_clause,
                    sh.status_value.ilike(f"%{value}%"),
                )
            )
        )

    if operator == "contains":
        pred = sh.status_value.ilike(f"%{value}%")
    elif operator == "startswith":
        pred = sh.status_value.ilike(f"{value}%")
    elif operator == "endswith":
        pred = sh.status_value.ilike(f"%{value}")
    elif operator == "eq":
        pred = sh.status_value == str(value)
    elif operator == "ne":
        pred = sh.status_value != str(value)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Operator {operator!r} is not supported for derived "
                "status filters (contains, ncontains, eq, ne, startswith, "
                "endswith)"
            ),
        )

    return sql.where(exists(select(1).where(base_clause, pred)))


def _thing_latest_open_status_sort_scalar(
    thing_table: type,
    status_type_literal: str,
):
    """Scalar subquery: ``status_value`` for the current open status row.

    Aligns with ``Thing.monitoring_status`` / ``Thing.well_status`` properties and
    with ``_apply_thing_derived_status_filter``: among rows with
    ``end_date IS NULL`` for this ``status_type``, pick the row with the
    maximum ``start_date``, then read ``status_value``.
    """
    from db.status_history import StatusHistory

    sh = StatusHistory
    tt = thing_table.__tablename__

    max_start = (
        select(func.max(sh.start_date))
        .select_from(sh)
        .where(
            sh.target_table == tt,
            sh.target_id == thing_table.id,
            sh.status_type == status_type_literal,
            sh.end_date.is_(None),
        )
        .correlate(thing_table)
        .scalar_subquery()
    )

    return (
        select(sh.status_value)
        .select_from(sh)
        .where(
            sh.target_table == tt,
            sh.target_id == thing_table.id,
            sh.status_type == status_type_literal,
            sh.end_date.is_(None),
            sh.start_date == max_start,
        )
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_site_name_sort_scalar(thing_table: type):
    """NMBGMR ``ThingIdLink.alternate_id`` with lowest link ``id`` (matches ``Thing.site_name``)."""
    from db.thing import ThingIdLink

    til = ThingIdLink
    return (
        select(til.alternate_id)
        .select_from(til)
        .where(
            til.thing_id == thing_table.id,
            til.alternate_organization == "NMBGMR",
        )
        .order_by(til.id.asc())
        .limit(1)
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_contacts_min_name_sort_scalar(thing_table: type):
    """Minimum ``lower(Contact.name)`` across associations (stable proxy for display order)."""
    from db.contact import Contact, ThingContactAssociation

    tca = ThingContactAssociation
    c = Contact
    return (
        select(func.min(func.lower(c.name)))
        .select_from(tca)
        .join(c, tca.contact_id == c.id)
        .where(
            tca.thing_id == thing_table.id,
            c.name.isnot(None),
        )
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_groups_min_name_sort_scalar(thing_table: type):
    """Minimum ``lower(Group.name)`` across linked projects (stable proxy for display order)."""
    from db.group import Group, GroupThingAssociation

    gta = GroupThingAssociation
    g = Group
    return (
        select(func.min(func.lower(g.name)))
        .select_from(gta)
        .join(g, gta.group_id == g.id)
        .where(
            gta.thing_id == thing_table.id,
            g.name.isnot(None),
        )
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_aquifers_min_name_sort_scalar(thing_table: type):
    """Minimum ``lower(AquiferSystem.name)`` across linked aquifers."""
    from db.aquifer_system import AquiferSystem
    from db.thing_aquifer_association import ThingAquiferAssociation

    taa = ThingAquiferAssociation
    aq = AquiferSystem
    return (
        select(func.min(func.lower(aq.name)))
        .select_from(taa)
        .join(aq, taa.aquifer_system_id == aq.id)
        .where(taa.thing_id == thing_table.id)
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_measuring_point_height_sort_scalar(thing_table: type):
    """Height from the latest ``MeasuringPointHistory`` row with non-null height."""
    from db.measuring_point_history import MeasuringPointHistory

    mph = MeasuringPointHistory
    return (
        select(mph.measuring_point_height)
        .select_from(mph)
        .where(
            mph.thing_id == thing_table.id,
            mph.measuring_point_height.isnot(None),
        )
        .order_by(mph.start_date.desc())
        .limit(1)
        .correlate(thing_table)
        .scalar_subquery()
    )


def _thing_open_status_order_expression(thing_table: type):
    """Rank ``Open`` before ``Closed``, unknown values last, no row second-to-last group."""
    sv = _thing_latest_open_status_sort_scalar(thing_table, "Open Status")
    return case(
        (sv.is_(None), 2),
        (sv == "Open", 0),
        (sv == "Closed", 1),
        else_=3,
    )


def _contact_things_min_name_sort_scalar(contact_table: type):
    """Minimum ``lower(Thing.name)`` across a contact's associated sites."""
    from db.contact import ThingContactAssociation
    from db.thing import Thing

    tca = ThingContactAssociation
    t = Thing
    return (
        select(func.min(func.lower(t.name)))
        .select_from(tca)
        .join(t, tca.thing_id == t.id)
        .where(
            tca.contact_id == contact_table.id,
            t.name.isnot(None),
        )
        .correlate(contact_table)
        .scalar_subquery()
    )


THING_VIRTUAL_SORT_FIELDS = frozenset(
    {
        "monitoring_status",
        "well_status",
        "datalogger_suitability_status",
        "site_name",
        "contacts",
        "groups",
        "aquifers",
        "open_status",
        "measuring_point_height",
    }
)


def _apply_thing_virtual_sort(
    sql: Select[Any],
    thing_table: type,
    sort: str,
    order: str,
) -> Select[Any] | None:
    """Apply SQL ``ORDER BY`` for Thing columns that are not mapped attributes."""
    if sort not in THING_VIRTUAL_SORT_FIELDS:
        return None

    ord_ = order.lower()
    if ord_ not in ("asc", "desc"):
        raise ValueError("Invalid order parameter. Use 'asc' or 'desc'.")

    def str_order(expr):
        if ord_ == "asc":
            return sql.order_by(
                nulls_last(expr.asc()),
                thing_table.id.asc(),
            )
        return sql.order_by(
            nulls_last(expr.desc()),
            thing_table.id.desc(),
        )

    def num_order(expr):
        if ord_ == "asc":
            return sql.order_by(
                nulls_last(expr.asc()),
                thing_table.id.asc(),
            )
        return sql.order_by(
            nulls_last(expr.desc()),
            thing_table.id.desc(),
        )

    if sort == "monitoring_status":
        expr = func.lower(
            _thing_latest_open_status_sort_scalar(thing_table, "Monitoring Status")
        )
        return str_order(expr)

    if sort == "well_status":
        expr = func.lower(
            _thing_latest_open_status_sort_scalar(thing_table, "Well Status")
        )
        return str_order(expr)

    if sort == "datalogger_suitability_status":
        expr = func.lower(
            _thing_latest_open_status_sort_scalar(
                thing_table, "Datalogger Suitability Status"
            )
        )
        return str_order(expr)

    if sort == "site_name":
        return str_order(func.lower(_thing_site_name_sort_scalar(thing_table)))

    if sort == "contacts":
        return str_order(_thing_contacts_min_name_sort_scalar(thing_table))

    if sort == "groups":
        return str_order(_thing_groups_min_name_sort_scalar(thing_table))

    if sort == "aquifers":
        return str_order(_thing_aquifers_min_name_sort_scalar(thing_table))

    if sort == "open_status":
        return num_order(_thing_open_status_order_expression(thing_table))

    if sort == "measuring_point_height":
        return num_order(_thing_measuring_point_height_sort_scalar(thing_table))

    raise NotImplementedError(
        f"Thing virtual sort {sort!r} is listed in THING_VIRTUAL_SORT_FIELDS "
        "but not implemented in _apply_thing_virtual_sort"
    )


def _apply_contact_virtual_sort(
    sql: Select[Any],
    contact_table: type,
    sort: str,
    order: str,
) -> Select[Any] | None:
    """Apply SQL ``ORDER BY`` for Contact columns that are not mapped columns."""
    if sort != "things":
        return None

    ord_ = order.lower()
    if ord_ not in ("asc", "desc"):
        raise ValueError("Invalid order parameter. Use 'asc' or 'desc'.")

    expr = func.lower(_contact_things_min_name_sort_scalar(contact_table))
    if ord_ == "asc":
        return sql.order_by(
            nulls_last(expr.asc()),
            contact_table.id.asc(),
        )
    return sql.order_by(
        nulls_last(expr.desc()),
        contact_table.id.desc(),
    )


def _apply_thing_contacts_filter(
    sql: Select[Any],
    thing_table: type,
    operator: str,
    value: Any,
) -> Select[Any]:
    """Filter ``Thing`` rows using linked contacts (many-to-many).

    **Why this exists.** The wells list exposes a ``contacts`` column backed by
    ``ThingContactAssociation``. Refine sends ``field=contacts``. That name is not
    a plain ``Thing`` column, so the default ILIKE path cannot apply.

    **Semantics.** Return wells where **any** linked contact satisfies the text
    operator on ``Contact.name`` (OR across association rows). We do **not**
    scan organization or role here; extend this function intentionally if those
    become product requirements.

    **SQL shape.** ``EXISTS`` avoids duplicating ``Thing`` rows when a well has
    multiple contacts (pagination stays one row per well).

    Pairing: ``_apply_contact_things_filter`` is the inverse direction for the
    contact list ``things`` column. See module comment and
    docs/refine-json-filters-and-virtual-fields.md.
    """
    from db.contact import Contact, ThingContactAssociation

    tca = ThingContactAssociation
    c = Contact

    def _linked_contact_select(predicate):
        return (
            select(1)
            .select_from(tca)
            .join(c, tca.contact_id == c.id)
            .where(
                tca.thing_id == thing_table.id,
                c.name.isnot(None),
                predicate,
            )
        )

    any_linked_contact = (
        select(1)
        .select_from(tca)
        .join(c, tca.contact_id == c.id)
        .where(tca.thing_id == thing_table.id)
    )

    if operator == "nnull":
        return sql.where(exists(any_linked_contact))

    if operator == "null":
        return sql.where(~exists(any_linked_contact))

    if operator == "ncontains":
        ncl = _linked_contact_select(c.name.ilike(f"%{value}%"))
        return sql.where(~exists(ncl))

    if operator == "ne":
        neq = _linked_contact_select(c.name == str(value))
        return sql.where(~exists(neq))

    if operator == "contains":
        pred = c.name.ilike(f"%{value}%")
    elif operator == "startswith":
        pred = c.name.ilike(f"{value}%")
    elif operator == "endswith":
        pred = c.name.ilike(f"%{value}")
    elif operator == "eq":
        pred = c.name == str(value)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Operator {operator!r} is not supported for contacts "
                "filters (contains, ncontains, eq, ne, startswith, endswith, "
                "null, nnull)"
            ),
        )

    return sql.where(exists(_linked_contact_select(pred)))


def _apply_thing_groups_filter(
    sql: Select[Any],
    thing_table: type,
    operator: str,
    value: Any,
) -> Select[Any]:
    """Filter ``Thing`` rows using linked groups / projects (many-to-many).

    Refine sends ``field=groups`` from the wells list when filtering by project.
    Match **any** linked ``Group`` by id (numeric ``eq``) or by ``Group.name``.
    """
    from db.group import Group, GroupThingAssociation

    gta = GroupThingAssociation
    g = Group

    def _linked_group_select(predicate):
        return (
            select(1)
            .select_from(gta)
            .join(g, gta.group_id == g.id)
            .where(
                gta.thing_id == thing_table.id,
                predicate,
            )
        )

    any_linked_group = (
        select(1)
        .select_from(gta)
        .join(g, gta.group_id == g.id)
        .where(gta.thing_id == thing_table.id)
    )

    if operator == "nnull":
        return sql.where(exists(any_linked_group))

    if operator == "null":
        return sql.where(~exists(any_linked_group))

    if operator == "eq":

        def _eq_predicate():
            try:
                group_id = int(value)
                return g.id == group_id
            except (TypeError, ValueError):
                return g.name == str(value)

        return sql.where(exists(_linked_group_select(_eq_predicate())))

    if operator == "ne":

        def _ne_predicate():
            try:
                group_id = int(value)
                return g.id == group_id
            except (TypeError, ValueError):
                return g.name == str(value)

        return sql.where(~exists(_linked_group_select(_ne_predicate())))

    if operator == "ncontains":
        nlg = _linked_group_select(g.name.ilike(f"%{value}%"))
        return sql.where(~exists(nlg))

    if operator == "contains":
        pred = g.name.ilike(f"%{value}%")
    elif operator == "startswith":
        pred = g.name.ilike(f"{value}%")
    elif operator == "endswith":
        pred = g.name.ilike(f"%{value}")
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Operator {operator!r} is not supported for groups "
                "filters (contains, ncontains, eq, ne, startswith, endswith, "
                "null, nnull)"
            ),
        )

    return sql.where(exists(_linked_group_select(pred)))


def _apply_contact_things_filter(
    sql: Select[Any],
    contact_table: type,
    operator: str,
    value: Any,
) -> Select[Any]:
    """Filter ``Contact`` rows using linked monitoring sites (many-to-many).

    **Why this exists.** The UI Associated Sites column summarizes related
    ``Thing`` rows. Refine sends ``field`` equal to ``things``. That relation is an
    association proxy on ``Contact``, not a searchable string column. Filters for
    Associated Sites must not go through the generic column ILIKE path (they would
    raise or behave incorrectly).

    **Semantics.** Keep contacts where **any** linked ``Thing.name`` matches
    the predicate (OR across ``ThingContactAssociation`` rows). Only ``name`` is
    searched for text operators, matching how the UI builds the display string
    from site names.

    **SQL shape.** ``EXISTS`` prevents one contact appearing multiple times when
    they own many sites.

    Inverse of ``_apply_thing_contacts_filter``. Narrative documentation:
    docs/refine-json-filters-and-virtual-fields.md.
    """
    from db.contact import ThingContactAssociation
    from db.thing import Thing

    tca = ThingContactAssociation
    t = Thing

    def _linked_thing_select(predicate):
        return (
            select(1)
            .select_from(tca)
            .join(t, tca.thing_id == t.id)
            .where(
                tca.contact_id == contact_table.id,
                t.name.isnot(None),
                predicate,
            )
        )

    any_linked_thing = (
        select(1)
        .select_from(tca)
        .join(t, tca.thing_id == t.id)
        .where(tca.contact_id == contact_table.id)
    )

    if operator == "nnull":
        return sql.where(exists(any_linked_thing))

    if operator == "null":
        return sql.where(~exists(any_linked_thing))

    if operator == "ncontains":
        nlk = _linked_thing_select(t.name.ilike(f"%{value}%"))
        return sql.where(~exists(nlk))

    if operator == "ne":
        neq = _linked_thing_select(t.name == str(value))
        return sql.where(~exists(neq))

    if operator == "contains":
        pred = t.name.ilike(f"%{value}%")
    elif operator == "startswith":
        pred = t.name.ilike(f"{value}%")
    elif operator == "endswith":
        pred = t.name.ilike(f"%{value}")
    elif operator == "eq":
        pred = t.name == str(value)
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Operator {operator!r} is not supported for things "
                "filters (contains, ncontains, eq, ne, startswith, endswith, "
                "null, nnull)"
            ),
        )

    return sql.where(exists(_linked_thing_select(pred)))


def _apply_json_filter_clause(
    sql: Select[Any], table: DeclarativeBase, f: dict
) -> Select[Any]:
    """Apply one Refine logical filter dict to an SQLAlchemy SELECT.

    Dispatch order matters. Virtual association branches (Contact ``things``,
    Thing ``contacts``, Thing derived statuses) **must** run before the generic
    ``getattr(table, field)`` path; otherwise proxies or unsupported types hit
    the column branch and produce 400 responses.

    Each call applies a **single** predicate. ``order_sort_filter`` chains
    multiple JSON filters with AND semantics.
    """
    required_keys = {"field", "value", "operator"}
    missing = required_keys - f.keys()
    if missing:
        keys = ", ".join(sorted(missing))
        raise HTTPException(
            status_code=422,
            detail=f"Missing required filter keys: {keys}",
        )

    field = f["field"]
    value = f["value"]
    operator = f["operator"]

    if getattr(table, "__name__", None) == "Thing" and field in (
        "monitoring_status",
        "well_status",
    ):
        status_type_map = {
            "monitoring_status": "Monitoring Status",
            "well_status": "Well Status",
        }
        return _apply_thing_derived_status_filter(
            sql, table, status_type_map[field], operator, value
        )

    if getattr(table, "__name__", None) == "Contact" and field == "things":
        return _apply_contact_things_filter(sql, table, operator, value)

    if getattr(table, "__name__", None) == "Thing" and field == "contacts":
        return _apply_thing_contacts_filter(sql, table, operator, value)

    if getattr(table, "__name__", None) == "Thing" and field == "groups":
        return _apply_thing_groups_filter(sql, table, operator, value)

    try:
        column = getattr(table, field)
    except AttributeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown filter field {field!r} for {table.__name__}",
        ) from exc

    py_t = _python_type(column)
    is_string = py_t is str or isinstance(column.type, (String, Text))

    if operator == "contains":
        if not is_string:
            raise HTTPException(
                status_code=400,
                detail=f"Operator contains is not supported for field {field!r}",
            )
        return sql.where(column.ilike(f"%{value}%"))

    if operator == "ncontains":
        if not is_string:
            raise HTTPException(
                status_code=400,
                detail=f"Operator ncontains is not supported for field {field!r}",
            )
        return sql.where(not_(column.ilike(f"%{value}%")))

    if operator == "startswith":
        if not is_string:
            raise HTTPException(
                status_code=400,
                detail=f"Operator startswith is not supported for field {field!r}",
            )
        return sql.where(column.ilike(f"{value}%"))

    if operator == "endswith":
        if not is_string:
            raise HTTPException(
                status_code=400,
                detail=f"Operator endswith is not supported for field {field!r}",
            )
        return sql.where(column.ilike(f"%{value}"))

    if operator == "eq":
        if py_t is float:
            return sql.where(column == float(value))
        if py_t is int:
            return sql.where(column == int(value))
        if is_string:
            return sql.where(column == str(value))
        return sql.where(column == value)

    if operator == "ne":
        if py_t is float:
            return sql.where(column != float(value))
        if py_t is int:
            return sql.where(column != int(value))
        if is_string:
            return sql.where(column != str(value))
        return sql.where(column != value)

    if operator == "gt":
        return sql.where(column > float(value) if py_t is float else column > value)

    if operator == "gte":
        return sql.where(column >= float(value) if py_t is float else column >= value)

    if operator == "lt":
        return sql.where(column < float(value) if py_t is float else column < value)

    if operator == "lte":
        return sql.where(column <= float(value) if py_t is float else column <= value)

    if operator == "null":
        return sql.where(column.is_(None))

    if operator == "nnull":
        return sql.where(column.is_not(None))

    if operator == "in":
        if not isinstance(value, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail="Operator in requires an array value",
            )
        return sql.where(column.in_(list(value)))

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported filter operator {operator!r}",
    )


def order_sort_filter(
    sql: Select[Any],
    table: DeclarativeBase,
    sort: str | None,
    order: str | None,
    filter_: str | None = None,
    *,
    filters: list[str] | None = None,
) -> Select[Any]:
    """Apply optional sort and zero or more Refine JSON filters to ``sql``.

    **Repeatable ``filter`` parameters.** Pass ``filters`` as the list of raw
    JSON strings from FastAPI ``Query(alias='filter')``. Each entry decodes to
    one predicate; all predicates are combined with AND. The legacy ``filter_``
    argument supports older callers that still pass a single JSON string.

    **Why both ``filter_`` and ``filters``.** Backward compatibility while we
    migrate every list route to list-shaped query params. UI clients should use
    repeated ``filter`` keys only.

    Virtual association fields are implemented inside
    ``_apply_json_filter_clause``. See
    docs/refine-json-filters-and-virtual-fields.md for background.
    """
    if order:
        if not sort:
            raise ValueError(
                "Sort parameter is required when order is specified. "
                f"The sort parameter should be a column name in the table {table}."
            )

        virtual_sorted = None
        if getattr(table, "__name__", None) == "Thing":
            virtual_sorted = _apply_thing_virtual_sort(sql, table, sort, order)
        elif getattr(table, "__name__", None) == "Contact":
            virtual_sorted = _apply_contact_virtual_sort(sql, table, sort, order)

        if virtual_sorted is not None:
            sql = virtual_sorted
        else:
            attr = getattr(table, sort)
            # test if column is a string col
            if isinstance(attr.type, String):
                attr = func.lower(attr)

            if order.lower() == "asc":
                sql = sql.order_by(attr.asc())
            elif order.lower() == "desc":
                sql = sql.order_by(attr.desc())
            else:
                raise ValueError("Invalid order parameter. Use 'asc' or 'desc'.")

    filter_jsons: list[str] = []
    if filters:
        filter_jsons.extend([x for x in filters if x])
    if filter_:
        filter_jsons.append(filter_)

    for raw in filter_jsons:
        try:
            f = json.loads(raw)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Invalid JSON in filter"
            ) from exc

        sql = _apply_json_filter_clause(sql, table, f)

    return sql


def paginated_all_getter(
    session, table, sort=None, order=None, filter_=None, sql=None
) -> Any:
    """
    Helper function to get all records from the database with pagination.
    """
    if sql is None:
        sql = select(table)

    sql = order_sort_filter(sql, table, sort, order, filter_)
    return paginate(query=sql, conn=session)


def searchable_getter(session, table, search, vector=None, joins=None) -> list[object]:
    if vector is None:
        vector = getattr(table, "search_vector", None)

    q = select(table)
    if joins:
        for join in joins:
            q = q.join(join)

    q = search_func(
        q,
        search,
        vector=vector,
    )
    return session.scalars(q).all()


# ============= EOF =============================================
