from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from starlette.responses import JSONResponse

from api.ogc.collections import get_collection, list_collections
from api.ogc.conformance import CONFORMANCE_CLASSES
from api.ogc.features import get_item, get_items
from api.ogc.schemas import Conformance, LandingPage
from core.dependencies import session_dependency, viewer_dependency

router = APIRouter(prefix="/ogc", tags=["ogc"])


@router.get("/")
def landing_page(request: Request) -> LandingPage:
    base = str(request.base_url).rstrip("/")
    return {
        "title": "Ocotillo OGC API",
        "description": "OGC API - Features endpoints",
        "links": [
            {
                "href": f"{base}/ogc",
                "rel": "self",
                "type": "application/json",
            },
            {
                "href": f"{base}/ogc/conformance",
                "rel": "conformance",
                "type": "application/json",
            },
            {
                "href": f"{base}/ogc/collections",
                "rel": "data",
                "type": "application/json",
            },
        ],
    }


@router.get("/conformance")
def conformance() -> Conformance:
    return {"conformsTo": CONFORMANCE_CLASSES}


@router.get("/collections")
def collections(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    payload = {
        "links": [
            {
                "href": f"{base}/ogc/collections",
                "rel": "self",
                "type": "application/json",
            }
        ],
        "collections": [c.model_dump() for c in list_collections(request)],
    }
    return JSONResponse(content=payload, media_type="application/json")


@router.get("/collections/{collection_id}")
def collection(request: Request, collection_id: str) -> JSONResponse:
    record = get_collection(request, collection_id)
    if record is None:
        return JSONResponse(status_code=404, content={"detail": "Collection not found"})
    return JSONResponse(content=record.model_dump(), media_type="application/json")


@router.get("/collections/{collection_id}/items")
def items(
    request: Request,
    user: viewer_dependency,
    session: session_dependency,
    collection_id: str,
    bbox: Annotated[str | None, Query(description="minx,miny,maxx,maxy")] = None,
    datetime: Annotated[str | None, Query(alias="datetime")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    properties: Annotated[str | None, Query(description="CQL filter")] = None,
    filter_: Annotated[str | None, Query(alias="filter")] = None,
    filter_lang: Annotated[str | None, Query(alias="filter-lang")] = None,
):
    payload = get_items(
        request,
        session,
        collection_id,
        bbox,
        datetime,
        limit,
        offset,
        properties,
        filter_,
        filter_lang,
    )
    return JSONResponse(content=payload, media_type="application/geo+json")


@router.get("/collections/{collection_id}/items/{fid}")
def item(
    request: Request,
    user: viewer_dependency,
    session: session_dependency,
    collection_id: str,
    fid: int,
):
    payload = get_item(request, session, collection_id, fid)
    return JSONResponse(content=payload, media_type="application/geo+json")
