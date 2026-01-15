from __future__ import annotations

from typing import Dict

from fastapi import Request

from api.ogc.schemas import Collection, CollectionExtent, CollectionExtentSpatial, Link


BASE_CRS = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


COLLECTIONS: Dict[str, dict] = {
    "locations": {
        "title": "Locations",
        "description": "Sample locations",
        "itemType": "feature",
    },
    "wells": {
        "title": "Wells",
        "description": "Things filtered to water wells",
        "itemType": "feature",
    },
    "springs": {
        "title": "Springs",
        "description": "Things filtered to springs",
        "itemType": "feature",
    },
}


def _collection_links(request: Request, collection_id: str) -> list[Link]:
    base = str(request.base_url).rstrip("/")
    return [
        Link(
            href=f"{base}/ogc/collections/{collection_id}",
            rel="self",
            type="application/json",
        ),
        Link(
            href=f"{base}/ogc/collections/{collection_id}/items",
            rel="items",
            type="application/geo+json",
        ),
        Link(
            href=f"{base}/ogc/collections",
            rel="collection",
            type="application/json",
        ),
    ]


def list_collections(request: Request) -> list[Collection]:
    collections = []
    for cid, meta in COLLECTIONS.items():
        extent = CollectionExtent(
            spatial=CollectionExtentSpatial(
                bbox=[[-180.0, -90.0, 180.0, 90.0]], crs=BASE_CRS
            )
        )
        collections.append(
            Collection(
                id=cid,
                title=meta["title"],
                description=meta.get("description"),
                itemType=meta.get("itemType", "feature"),
                crs=[BASE_CRS],
                links=_collection_links(request, cid),
                extent=extent,
            )
        )
    return collections


def get_collection(request: Request, collection_id: str) -> Collection | None:
    meta = COLLECTIONS.get(collection_id)
    if not meta:
        return None
    extent = CollectionExtent(
        spatial=CollectionExtentSpatial(
            bbox=[[-180.0, -90.0, 180.0, 90.0]], crs=BASE_CRS
        )
    )
    return Collection(
        id=collection_id,
        title=meta["title"],
        description=meta.get("description"),
        itemType=meta.get("itemType", "feature"),
        crs=[BASE_CRS],
        links=_collection_links(request, collection_id),
        extent=extent,
    )
