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
from sqlalchemy import Column, Float, Integer, Select, String, Text, func, not_, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql.elements import OperatorExpression
from starlette.status import HTTP_404_NOT_FOUND

from db import search as search_func
from services.env import to_bool
from services.regex import QUERY_REGEX


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


def _apply_json_filter_clause(
    sql: Select[Any], table: DeclarativeBase, f: dict
) -> Select[Any]:
    """Apply one Refine logical filter dict (field / operator / value) to a SELECT."""
    required_keys = {"field", "value", "operator"}
    missing = required_keys - f.keys()
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required filter keys: {', '.join(sorted(missing))}",
        )

    field = f["field"]
    value = f["value"]
    operator = f["operator"]

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
    if order:
        if not sort:
            raise ValueError(
                "Sort parameter is required when order is specified. "
                f"The sort parameter should be a column name in the table {table}."
            )

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
