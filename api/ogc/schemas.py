from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Link(BaseModel):
    href: str
    rel: str
    type: Optional[str] = None
    title: Optional[str] = None


class LandingPage(BaseModel):
    title: str
    description: str
    links: List[Link]


class Conformance(BaseModel):
    conformsTo: List[str] = Field(default_factory=list)


class CollectionExtentSpatial(BaseModel):
    bbox: List[List[float]]
    crs: str


class CollectionExtentTemporal(BaseModel):
    interval: List[List[Optional[str]]]
    trs: Optional[str] = None


class CollectionExtent(BaseModel):
    spatial: Optional[CollectionExtentSpatial] = None
    temporal: Optional[CollectionExtentTemporal] = None


class Collection(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    itemType: str = "feature"
    crs: Optional[List[str]] = None
    links: List[Link]
    extent: Optional[CollectionExtent] = None


class Collections(BaseModel):
    links: List[Link]
    collections: List[Collection]


class Feature(BaseModel):
    type: str = "Feature"
    id: str | int
    geometry: dict[str, Any]
    properties: dict[str, Any]


class FeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[Feature]
    links: List[Link]
    numberMatched: int
    numberReturned: int
