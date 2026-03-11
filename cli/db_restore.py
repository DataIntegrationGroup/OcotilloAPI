import getpass
import gzip
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from db.engine import engine, session_ctx
from db.initialization import recreate_public_schema
from services.gcs_helper import get_storage_bucket

LOCAL_POSTGRES_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}
ROLE_DEPENDENT_SQL_PATTERNS = (
    re.compile(r"^\s*SET\s+ROLE\b", re.IGNORECASE),
    re.compile(r"^\s*SET\s+SESSION\s+AUTHORIZATION\b", re.IGNORECASE),
    re.compile(r"^\s*ALTER\s+.*\s+OWNER\s+TO\b", re.IGNORECASE),
    re.compile(r"^\s*GRANT\b", re.IGNORECASE),
    re.compile(r"^\s*REVOKE\b", re.IGNORECASE),
    re.compile(r"^\s*ALTER\s+DEFAULT\s+PRIVILEGES\b", re.IGNORECASE),
)


class LocalDbRestoreError(RuntimeError):
    """Raised when a local database restore cannot be performed safely."""


@dataclass(frozen=True)
class LocalDbRestoreResult:
    sql_file: Path
    source: str
    host: str
    port: str
    user: str
    db_name: str


def _is_gcs_uri(source: str) -> bool:
    return source.startswith("gs://")


def _parse_gcs_uri(source: str) -> tuple[str, str]:
    if not _is_gcs_uri(source):
        raise LocalDbRestoreError(f"Expected gs:// URI, got {source!r}.")

    path = source[5:]
    bucket_name, _, blob_name = path.partition("/")
    if not bucket_name or not blob_name:
        raise LocalDbRestoreError(
            f"Invalid GCS URI {source!r}; expected gs://bucket/path.sql[.gz]."
        )
    return bucket_name, blob_name


def _validate_restore_source_name(source_name: str) -> None:
    if source_name.endswith(".sql") or source_name.endswith(".sql.gz"):
        return

    raise LocalDbRestoreError(
        "restore-local-db requires a .sql or .sql.gz source; " f"got {source_name!r}."
    )


def _decompress_gzip_file(source_path: Path, target_path: Path) -> None:
    with gzip.open(source_path, "rb") as compressed:
        with open(target_path, "wb") as expanded:
            while chunk := compressed.read(1024 * 1024):
                expanded.write(chunk)


def _sanitize_sql_dump(source_path: Path, target_path: Path) -> None:
    with open(source_path, "r", encoding="utf-8") as infile:
        with open(target_path, "w", encoding="utf-8") as outfile:
            for line in infile:
                if any(pattern.search(line) for pattern in ROLE_DEPENDENT_SQL_PATTERNS):
                    continue
                outfile.write(line)


@contextmanager
def _stage_restore_source(source: str | Path):
    source_text = str(source)
    _validate_restore_source_name(source_text)

    with tempfile.TemporaryDirectory(prefix="ocotillo-db-restore-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        expanded_sql_path = temp_dir_path / "expanded.sql"
        staged_sql_path = temp_dir_path / "restore.sql"

        if _is_gcs_uri(source_text):
            bucket_name, blob_name = _parse_gcs_uri(source_text)
            bucket = get_storage_bucket(bucket=bucket_name)
            blob = bucket.blob(blob_name)
            downloaded_path = temp_dir_path / Path(blob_name).name
            blob.download_to_filename(str(downloaded_path))

            if source_text.endswith(".sql.gz"):
                _decompress_gzip_file(downloaded_path, expanded_sql_path)
            else:
                expanded_sql_path = downloaded_path
            _sanitize_sql_dump(expanded_sql_path, staged_sql_path)
            yield staged_sql_path, source_text
            return

        source_path = Path(source_text)
        if not source_path.exists():
            raise LocalDbRestoreError(f"Restore source not found: {source_path}")
        if not source_path.is_file():
            raise LocalDbRestoreError(f"Restore source is not a file: {source_path}")

        if source_text.endswith(".sql.gz"):
            _decompress_gzip_file(source_path, expanded_sql_path)
        else:
            expanded_sql_path = source_path
        _sanitize_sql_dump(expanded_sql_path, staged_sql_path)
        yield staged_sql_path, str(source_path)


def _resolve_restore_target(
    db_name: str | None = None,
) -> tuple[str, str, str, str, str]:
    driver = (os.environ.get("DB_DRIVER") or "").strip().lower()
    if driver == "cloudsql":
        raise LocalDbRestoreError(
            "restore-local-db only supports local PostgreSQL targets; "
            "DB_DRIVER=cloudsql is not allowed."
        )

    host = (os.environ.get("POSTGRES_HOST") or "localhost").strip()
    if not host:
        host = "localhost"
    if host not in LOCAL_POSTGRES_HOSTS:
        raise LocalDbRestoreError(
            "restore-local-db only supports local PostgreSQL hosts "
            f"({', '.join(sorted(LOCAL_POSTGRES_HOSTS))}); got {host!r}."
        )

    port = (os.environ.get("POSTGRES_PORT") or "5432").strip()
    if not port:
        port = "5432"

    user = (os.environ.get("POSTGRES_USER") or "").strip()
    if not user:
        user = getpass.getuser()

    target_db = (db_name or os.environ.get("POSTGRES_DB") or "postgres").strip()
    if not target_db:
        raise LocalDbRestoreError("Target database name is empty.")

    password = os.environ.get("POSTGRES_PASSWORD", "")
    return host, port, user, target_db, password


def _reset_target_schema() -> None:
    try:
        engine.dispose()
        with session_ctx() as session:
            recreate_public_schema(session)
        engine.dispose()
    except Exception as exc:
        raise LocalDbRestoreError(
            f"Failed to reset the public schema before restore: {exc}"
        ) from exc


def restore_local_db_from_sql(
    source_file: Path | str, *, db_name: str | None = None
) -> LocalDbRestoreResult:
    host, port, user, target_db, password = _resolve_restore_target(db_name)
    with _stage_restore_source(source_file) as (staged_sql_file, source_description):
        try:
            _reset_target_schema()
        except LocalDbRestoreError:
            raise
        except Exception as exc:
            raise LocalDbRestoreError(
                f"Failed to reset the public schema before restore: {exc}"
            ) from exc
        command = [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            target_db,
            "-f",
            str(staged_sql_file),
        ]

        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password

        try:
            subprocess.run(
                command,
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise LocalDbRestoreError(
                "psql is not installed or not available on PATH."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip() or str(exc)
            raise LocalDbRestoreError(
                f"Restore failed for database {target_db!r}: {detail}"
            ) from exc

        return LocalDbRestoreResult(
            sql_file=staged_sql_file,
            source=source_description,
            host=host,
            port=port,
            user=user,
            db_name=target_db,
        )
