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
from sqlalchemy import select, Float, Integer
from db import search as search_func
from services.regex import QUERY_REGEX


def to_bool(value: str) -> bool | str:
    """Convert a string to a boolean."""
    if isinstance(value, bool):
        return value
    if value.lower() in ("true", "1", "yes"):
        return True
    elif value.lower() in ("false", "0", "no"):
        return False

    return value


def make_where(col, op: str, v: str):

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


def make_query(table, query: str):
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


# ============= EOF =============================================
def simple_get_by_name(session, table, name):
    """
    Helper function to get a record by name from the database.
    """
    sql = select(table).where(table.name == name)
    result = session.execute(sql)
    return result.scalar_one_or_none()


def simple_get_by_id(session, table, item_id):
    """
    Helper function to get a record by ID from the database.
    """
    sql = select(table).where(table.id == item_id)
    result = session.execute(sql)
    return result.scalar_one_or_none()


def simple_all_getter(session, table):
    """
    Helper function to get records from the database.
    """
    sql = select(table)
    return session.scalars(sql).all()
    # result = session.execute(sql)
    # return result.scalars().all()


def searchable_getter(session, table, search, vector=None, joins=None):
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
