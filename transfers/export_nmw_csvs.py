"""Export NM_Wells SQL Server tables to CSV files for the transfer pipeline.

Connects to the NM_Wells SQL Server database and exports each source table to
transfers/data/nma_csv_cache/<table>.csv, which is where nmw_mirror_transfer.py
looks for them when NMW_SQL_DUMP is not set.

Usage:
    uv run python -m transfers.export_nmw_csvs

Required environment variables (add to .env):
    NMW_HOST      SQL Server hostname or IP
    NMW_PORT      SQL Server port (default: 1433)
    NMW_USER      SQL Server username
    NMW_PASSWORD  SQL Server password
    NMW_DATABASE  Database name (default: NM_Wells)
"""

import os
from pathlib import Path

import pymssql
from dotenv import load_dotenv

from transfers.nmw_mirror_transfer import NMW_MIRROR_SPECS

load_dotenv(override=False)

TABLES = [spec.source_table for spec in NMW_MIRROR_SPECS]

OUT_DIR = Path(__file__).parent / "data" / "nma_csv_cache"


def _get_connection():
    host = os.environ["NMW_HOST"]
    port = int(os.environ.get("NMW_PORT", 1433))
    user = os.environ["NMW_USER"]
    password = os.environ["NMW_PASSWORD"]
    database = os.environ.get("NMW_DATABASE", "NM_Wells")
    return pymssql.connect(
        server=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def export_table(cursor, table: str, out_path: Path) -> int:
    cursor.execute(f"SELECT * FROM dbo.{table}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    import csv

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    return len(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"Connecting to {os.environ.get('NMW_HOST')} / {os.environ.get('NMW_DATABASE', 'NM_Wells')}"
    )
    conn = _get_connection()
    cursor = conn.cursor()

    for table in TABLES:
        out_path = OUT_DIR / f"{table}.csv"
        print(f"  Exporting {table}...", end=" ", flush=True)
        try:
            n = export_table(cursor, table, out_path)
            print(f"{n} rows -> {out_path.name}")
        except Exception as e:
            print(f"FAILED: {e}")

    cursor.close()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
