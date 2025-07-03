from fastapi_pagination import Page
from fastapi_pagination.customization import UseName, UseParamsFields, CustomizedPage
from fastapi import Query

MAX_PAGINATION_SIZE = 10000

CustomPage = CustomizedPage[
    Page,
    UseName("Page"),
    UseParamsFields(
        size=Query(25, ge=1, le=MAX_PAGINATION_SIZE),
    ),
]
