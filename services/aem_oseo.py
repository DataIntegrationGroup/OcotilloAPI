# flake8: noqa: E501
"""GeoServer OpenSearch for EO provisioning and ingest helpers for AEM."""

from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as etree

import pandas as pd
import requests
from geo.Geoserver import Geoserver, GeoserverException
from shapely.geometry import box, mapping

from schemas.aem import IngestConfig, SURVEY_METADATA
from services.aem_db import get_raw_connection
from services.aem_parsers.common import TARGET_EPSG
from services.util import transform_srid


@dataclass(frozen=True)
class OseoConfig:
    geoserver_url: str
    username: str
    password: str
    workspace: str
    postgis_store: str
    oseo_store: str
    schema: str
    timeout: float = 30.0

    @property
    def rest_url(self) -> str:
        return f"{self.geoserver_url}/rest"

    @property
    def oseo_url(self) -> str:
        return f"{self.geoserver_url}/oseo/rest"

    @property
    def qualified_postgis_store(self) -> str:
        return f"{self.workspace}:{self.postgis_store}"

    @property
    def qualified_oseo_store(self) -> str:
        return f"{self.workspace}:{self.oseo_store}"


def load_oseo_config() -> OseoConfig | None:
    """Load GeoServer/OpenSearch for EO config from environment variables."""
    url = os.environ.get("GEOSERVER_URL") or os.environ.get("AEM_GEOSERVER_URL")
    username = (
        os.environ.get("GEOSERVER_USERNAME")
        or os.environ.get("GEOSERVER_USER")
        or os.environ.get("AEM_GEOSERVER_USERNAME")
    )
    password = os.environ.get("GEOSERVER_PASSWORD") or os.environ.get(
        "AEM_GEOSERVER_PASSWORD"
    )
    if not (url and username and password):
        return None

    return OseoConfig(
        geoserver_url=url.rstrip("/"),
        username=username,
        password=password,
        workspace=os.environ.get("GEOSERVER_WORKSPACE", "aem"),
        postgis_store=os.environ.get("GEOSERVER_OSEO_POSTGIS_STORE", "oseo_metadata"),
        oseo_store=os.environ.get("GEOSERVER_OSEO_STORE", "oseo_jdbc"),
        schema=os.environ.get("GEOSERVER_OSEO_SCHEMA", "stac"),
        timeout=float(os.environ.get("GEOSERVER_TIMEOUT", "30")),
    )


def provision_oseo_services(config: OseoConfig) -> None:
    """Ensure GeoServer is configured to serve the OSEO schema."""
    geoserver = _build_geoserver_client(config)
    session = _build_oseo_session(config)
    ensure_workspace(geoserver, config)
    ensure_postgis_store(geoserver, config)
    ensure_oseo_store(session, config)
    configure_oseo_service(session, config)


def ingest_oseo_metadata(
    df: pd.DataFrame,
    config: IngestConfig,
    oseo_config: OseoConfig,
) -> dict[str, str]:
    """Upsert OSEO collection/product metadata through the admin REST API."""
    session = _build_oseo_session(oseo_config)

    collection_payload = build_collection_package(config, oseo_config)
    _put_zip(
        session,
        f"{oseo_config.oseo_url}/collections",
        collection_payload,
        "collection.zip",
    )

    product_id = build_product_id(config)
    product_payload = build_product_package(
        df,
        config,
        product_id,
    )
    response = _post_zip(
        session,
        f"{oseo_config.oseo_url}/collections/{config.survey_id}/products",
        product_payload,
        "product.zip",
        ok_statuses={200, 201},
        conflict_ok=True,
    )
    if response is not None and response.status_code == 409:
        _put_zip(
            session,
            (
                f"{oseo_config.oseo_url}/collections/{config.survey_id}/products/"
                f"{product_id}"
            ),
            product_payload,
            "product.zip",
        )

    return {"collection_id": config.survey_id, "product_id": product_id}


def _build_geoserver_client(config: OseoConfig) -> Geoserver:
    return Geoserver(
        service_url=config.geoserver_url,
        username=config.username,
        password=config.password,
        request_options={"timeout": config.timeout},
    )


def _build_oseo_session(config: OseoConfig) -> requests.Session:
    session = requests.Session()
    session.auth = (config.username, config.password)
    session.headers.update({"Accept": "application/xml, application/json"})
    session._oseo_timeout = config.timeout
    return session


def ensure_workspace(geoserver: Geoserver, config: OseoConfig) -> None:
    try:
        geoserver.get_workspace(config.workspace)
        return
    except GeoserverException as exc:
        if exc.status != 404:
            raise RuntimeError(f"workspace lookup failed: {exc}") from exc
    try:
        geoserver.create_workspace(config.workspace)
    except GeoserverException as exc:
        raise RuntimeError(f"workspace creation failed: {exc}") from exc


def ensure_postgis_store(geoserver: Geoserver, config: OseoConfig) -> None:
    try:
        geoserver.get_datastore(config.postgis_store, workspace=config.workspace)
        return
    except GeoserverException as exc:
        if exc.status != 404:
            raise RuntimeError(f"PostGIS datastore lookup failed: {exc}") from exc

    try:
        geoserver.create_featurestore(
            store_name=config.postgis_store,
            workspace=config.workspace,
            db=os.environ["POSTGRES_DB"],
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            schema=config.schema,
            pg_user=os.environ["POSTGRES_USER"],
            pg_password=os.environ["POSTGRES_PASSWORD"],
            expose_primary_keys="true",
            overwrite=False,
        )
    except GeoserverException as exc:
        raise RuntimeError(f"PostGIS datastore creation failed: {exc}") from exc


def ensure_oseo_store(session: requests.Session, config: OseoConfig) -> None:
    response = session.get(
        (
            f"{config.rest_url}/workspaces/{config.workspace}/datastores/"
            f"{config.oseo_store}.xml"
        ),
        timeout=config.timeout,
    )
    if response.status_code == 200:
        return
    if response.status_code != 404:
        _raise_geoserver_error(response, "OSEO datastore lookup failed")

    errors = []
    for store_type in ("JDBCOpenSearchAccess", "JDBC based OpenSearch store"):
        payload = build_oseo_store_xml(config, store_type=store_type)
        response = session.post(
            f"{config.rest_url}/workspaces/{config.workspace}/datastores",
            data=payload,
            headers={"Content-Type": "application/xml"},
            timeout=config.timeout,
        )
        if response.status_code in {200, 201}:
            return
        errors.append(f"{store_type}: {response.status_code} {response.text}")

    raise RuntimeError("Unable to create OSEO datastore. " + " | ".join(errors))


def configure_oseo_service(session: requests.Session, config: OseoConfig) -> None:
    url = f"{config.rest_url}/services/oseo/settings.xml"
    response = session.get(url, timeout=config.timeout)
    if response.status_code not in {200, 404}:
        _raise_geoserver_error(response, "OSEO settings lookup failed")

    if response.status_code == 200 and response.text.strip():
        root = etree.fromstring(response.text)
    else:
        root = etree.Element("oseo")
        etree.SubElement(root, "name").text = "OSEO"

    _set_xml_text(root, "enabled", "true")

    store_tag = None
    for child in root:
        if "store" in child.tag.lower():
            store_tag = child.tag
            break
    if store_tag is None:
        store_tag = "openSearchAccessStore"
    _set_xml_text(root, store_tag, config.qualified_oseo_store)

    payload = etree.tostring(root, encoding="utf-8")
    response = session.put(
        url,
        data=payload,
        headers={"Content-Type": "application/xml"},
        timeout=config.timeout,
    )
    if response.status_code not in {200, 201}:
        _raise_geoserver_error(response, "OSEO settings update failed")


def _set_xml_text(root: etree.Element, tag: str, value: str) -> None:
    node = root.find(tag)
    if node is None:
        node = etree.SubElement(root, tag)
    node.text = value


def build_postgis_store_xml(config: OseoConfig) -> str:
    env = os.environ
    return f"""
<dataStore>
  <name>{config.postgis_store}</name>
  <type>PostGIS</type>
  <enabled>true</enabled>
  <connectionParameters>
    <entry key="dbtype">postgis</entry>
    <entry key="host">{env["POSTGRES_HOST"]}</entry>
    <entry key="port">{env.get("POSTGRES_PORT", "5432")}</entry>
    <entry key="database">{env["POSTGRES_DB"]}</entry>
    <entry key="user">{env["POSTGRES_USER"]}</entry>
    <entry key="passwd">{env["POSTGRES_PASSWORD"]}</entry>
    <entry key="schema">{config.schema}</entry>
    <entry key="Expose primary keys">true</entry>
  </connectionParameters>
</dataStore>
""".strip()


def build_oseo_store_xml(config: OseoConfig, store_type: str) -> str:
    return f"""
<dataStore>
  <name>{config.oseo_store}</name>
  <type>{store_type}</type>
  <enabled>true</enabled>
  <connectionParameters>
    <entry key="store">{config.qualified_postgis_store}</entry>
  </connectionParameters>
</dataStore>
""".strip()


def build_product_id(config: IngestConfig) -> str:
    stem = Path(config.source_gcs_path).stem.lower().replace(".", "_")
    return f"{config.survey_id}_{config.processing_stage.value}_{stem}"


def build_collection_package(
    ingest_config: IngestConfig,
    oseo_config: OseoConfig,
) -> bytes:
    summary = query_collection_summary(ingest_config.survey_id)
    metadata = SURVEY_METADATA.get(ingest_config.survey_id)
    title = metadata.survey_region if metadata else ingest_config.survey_id
    system = metadata.system if metadata else ingest_config.inversion_code.value

    collection = {
        "name": ingest_config.survey_id,
        "title": title,
        "description": f"AEM survey {ingest_config.survey_id}",
        "primary": True,
        "footprint": summary["footprint"],
        "timeStart": summary["time_start"],
        "timeEnd": summary["time_end"],
        "eo:identifier": ingest_config.survey_id,
        "eo:productType": "aem",
        "eo:platform": "Airborne EM",
        "eo:instrument": [system],
        "workspaces": [oseo_config.workspace],
    }
    return build_oseo_zip({"collection.json": json.dumps(collection, indent=2)})


def build_product_package(
    df: pd.DataFrame,
    ingest_config: IngestConfig,
    product_id: str,
) -> bytes:
    summary = summarize_product_dataframe(df)
    source_ext = Path(ingest_config.source_gcs_path).suffix.lower() or ".dat"
    product = {
        "eo:identifier": product_id,
        "eo:parentIdentifier": ingest_config.survey_id,
        "footprint": summary["footprint"],
        "timeStart": summary["time_start"],
        "timeEnd": summary["time_end"],
        "originalPackageLocation": (
            f"gs://{ingest_config.gcs_bucket}/{ingest_config.source_gcs_path}"
        ),
        "originalPackageType": source_ext.lstrip("."),
        "eo:processorName": ingest_config.inversion_code.value,
        "eo:processingMode": ingest_config.processing_stage.value,
    }
    return build_oseo_zip({"product.json": json.dumps(product, indent=2)})


def build_oseo_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def query_collection_summary(survey_id: str) -> dict[str, Any]:
    raw_conn = get_raw_connection()
    cur = raw_conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                ST_AsGeoJSON(ST_Envelope(ST_Collect(geom))) AS footprint,
                MIN(date_acquired) AS time_start,
                MAX(date_acquired) AS time_end
            FROM aem_soundings
            WHERE survey_id = %s
            """,
            (survey_id,),
        )
        footprint_json, time_start, time_end = cur.fetchone()
    finally:
        cur.close()
        raw_conn.close()

    return {
        "footprint": json.loads(footprint_json),
        "time_start": _to_oseo_timestamp(time_start),
        "time_end": _to_oseo_timestamp(time_end),
    }


def summarize_product_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    bbox = box(
        float(df["easting"].min()),
        float(df["northing"].min()),
        float(df["easting"].max()),
        float(df["northing"].max()),
    )
    footprint = transform_srid(bbox, TARGET_EPSG, 4326)

    dates = (
        pd.to_datetime(df["date_acquired"].dropna())
        if "date_acquired" in df.columns
        else pd.Series(dtype="datetime64[ns]")
    )
    time_start = dates.min() if not dates.empty else None
    time_end = dates.max() if not dates.empty else None

    return {
        "footprint": mapping(footprint),
        "time_start": _to_oseo_timestamp(time_start),
        "time_end": _to_oseo_timestamp(time_end),
    }


def _to_oseo_timestamp(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _put_zip(
    session: requests.Session,
    url: str,
    payload: bytes,
    filename: str,
) -> requests.Response:
    response = session.put(
        url,
        files={"file": (filename, payload, "application/zip")},
        timeout=_timeout_from_session(session),
    )
    if response.status_code not in {200, 201}:
        _raise_geoserver_error(response, f"ZIP PUT failed for {url}")
    return response


def _post_zip(
    session: requests.Session,
    url: str,
    payload: bytes,
    filename: str,
    ok_statuses: set[int],
    conflict_ok: bool = False,
) -> requests.Response | None:
    response = session.post(
        url,
        files={"file": (filename, payload, "application/zip")},
        timeout=_timeout_from_session(session),
    )
    if response.status_code in ok_statuses:
        return response
    if conflict_ok and response.status_code == 409:
        return response
    _raise_geoserver_error(response, f"ZIP POST failed for {url}")
    return None


def _timeout_from_session(session: requests.Session) -> float:
    timeout = getattr(session, "_oseo_timeout", None)
    return float(timeout) if timeout is not None else 30.0


def _raise_geoserver_error(response: requests.Response, message: str) -> None:
    raise RuntimeError(f"{message}: {response.status_code} {response.text}")
