import asyncio

import pytest
from fastapi import FastAPI
from fastapi_pagination import add_pagination, paginate
from httpx import ASGITransport, AsyncClient

from api.pagination import CustomPage, MAX_PAGINATION_SIZE


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """These in-memory pagination checks do not need the database fixture."""


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/items", response_model=CustomPage[int])
    async def items():
        return paginate(list(range(60)))

    # This raised during application startup with FastAPI 0.161.1.
    add_pagination(app)
    return app


def get(app, url):
    async def request():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(url)

    return asyncio.run(request())


@pytest.mark.parametrize(
    "query,page,size,items,pages",
    [
        ("", 1, 25, list(range(25)), 3),
        ("?page=2&size=10", 2, 10, list(range(10, 20)), 6),
        ("?page=4&size=25", 4, 25, [], 3),
        ("?size=10000", 1, 10000, list(range(60)), 1),
    ],
)
def test_pagination_response(app, query, page, size, items, pages):
    response = get(app, f"/items{query}")
    assert response.status_code == 200
    assert response.json() == {
        "items": items,
        "total": 60,
        "page": page,
        "size": size,
        "pages": pages,
    }


@pytest.mark.parametrize(
    "query,field",
    [
        ("page=0", "page"),
        ("size=0", "size"),
        ("size=10001", "size"),
        ("page=invalid", "page"),
        ("size=invalid", "size"),
    ],
)
def test_pagination_rejects_invalid_parameters(app, query, field):
    response = get(app, f"/items?{query}")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


def test_pagination_openapi_contract(app):
    operation = app.openapi()["paths"]["/items"]["get"]
    params = {param["name"]: param for param in operation["parameters"]}
    assert set(params) == {"page", "size"}
    for name, default in [("page", 1), ("size", 25)]:
        assert params[name]["in"] == "query"
        assert params[name]["required"] is False
        assert params[name]["schema"]["type"] == "integer"
        assert params[name]["schema"]["default"] == default
        assert params[name]["schema"]["minimum"] == 1
    assert params["page"]["description"] == "Page number"
    assert params["size"]["schema"]["maximum"] == MAX_PAGINATION_SIZE
