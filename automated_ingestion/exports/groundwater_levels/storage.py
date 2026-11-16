# ===============================================================================
# Copyright 2026 ross
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
"""
Where the export reads and writes: a GCS prefix, or a local directory.

The steps only need whole-object reads and writes, so this is deliberately
small. The local implementation exists so the full pipeline -- snapshot through
STAC -- runs in tests and on a laptop without a bucket.

Export storage is its own root (``GWL_EXPORT_ROOT``), never the API's uploads
bucket or the ingestion raw zone: those hold private data, and this one is
published.
"""

import json
import os
from pathlib import Path
from typing import Any, Protocol


class Storage(Protocol):
    root: str

    def read_bytes(self, path: str) -> bytes: ...

    def write_bytes(
        self, path: str, data: bytes, content_type: str | None = None
    ) -> None: ...

    def exists(self, path: str) -> bool: ...

    def delete(self, path: str) -> None: ...

    def copy(self, src: str, dst: str) -> None: ...

    def list(self, prefix: str) -> list[str]: ...


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = str(root)
        self._root = Path(root)

    def _path(self, path: str) -> Path:
        resolved = (self._root / path).resolve()
        if self._root.resolve() not in resolved.parents and resolved != self._root:
            raise ValueError(f"{path!r} escapes the export root")
        return resolved

    def read_bytes(self, path: str) -> bytes:
        return self._path(path).read_bytes()

    def write_bytes(self, path: str, data: bytes, content_type=None) -> None:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def exists(self, path: str) -> bool:
        return self._path(path).exists()

    def delete(self, path: str) -> None:
        self._path(path).unlink(missing_ok=True)

    def copy(self, src: str, dst: str) -> None:
        self.write_bytes(dst, self.read_bytes(src))

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        return sorted(
            str(p.relative_to(self._root)) for p in base.rglob("*") if p.is_file()
        )


class GCSStorage:
    """A ``gs://bucket[/prefix]`` root, through google-cloud-storage."""

    def __init__(self, url: str, client: Any = None):
        if not url.startswith("gs://"):
            raise ValueError(f"not a gs:// url: {url!r}")
        bucket, _, prefix = url[len("gs://") :].partition("/")
        self.root = url.rstrip("/")
        self._prefix = prefix.strip("/")
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._bucket = client.bucket(bucket)

    def _key(self, path: str) -> str:
        return f"{self._prefix}/{path}" if self._prefix else path

    def read_bytes(self, path: str) -> bytes:
        return self._bucket.blob(self._key(path)).download_as_bytes()

    def write_bytes(self, path: str, data: bytes, content_type=None) -> None:
        blob = self._bucket.blob(self._key(path))
        blob.upload_from_string(data, content_type=content_type)

    def exists(self, path: str) -> bool:
        return self._bucket.blob(self._key(path)).exists()

    def delete(self, path: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self._bucket.blob(self._key(path)).delete()
        except NotFound:
            pass

    def copy(self, src: str, dst: str) -> None:
        source = self._bucket.blob(self._key(src))
        self._bucket.copy_blob(source, self._bucket, self._key(dst))

    def list(self, prefix: str) -> list[str]:
        strip = len(self._prefix) + 1 if self._prefix else 0
        return sorted(
            b.name[strip:] for b in self._bucket.list_blobs(prefix=self._key(prefix))
        )


ROOT_ENV_VAR = "GWL_EXPORT_ROOT"


def open_storage(root: str | None = None) -> Storage:
    """Storage for ``root``, or for ``GWL_EXPORT_ROOT`` when none is given.

    Raises rather than defaulting, for the same reason as the raw zone: a
    guessed root is a run that reports success while publishing nowhere.
    """
    root = (root or os.environ.get(ROOT_ENV_VAR, "")).strip()
    if not root:
        raise RuntimeError(
            f"{ROOT_ENV_VAR} is not set. Set it to the export bucket "
            "(gs://ocotillo-timeseries-<env>) Terraform created."
        )
    for reserved in ("GCS_BUCKET_NAME", "INGESTION_GCS_BUCKET"):
        other = os.environ.get(reserved, "").strip()
        if other and root.removeprefix("gs://").split("/")[0] == other:
            raise RuntimeError(
                f"{ROOT_ENV_VAR} points at {reserved}. The export bucket is "
                "public; that one is not."
            )
    if root.startswith("gs://"):
        return GCSStorage(root)
    return LocalStorage(root)


def read_json(storage: Storage, path: str, default: Any = None) -> Any:
    if default is not None and not storage.exists(path):
        return default
    return json.loads(storage.read_bytes(path))


def write_json(storage: Storage, path: str, value: Any) -> None:
    storage.write_bytes(
        path,
        json.dumps(value, indent=2, sort_keys=True, default=str).encode(),
        content_type="application/json",
    )


# ============= EOF =============================================
