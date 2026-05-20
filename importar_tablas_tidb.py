#!/usr/bin/env python3
"""Importa tablas faltantes a TiDB (ucs2, fechas 0000-00-00, LOCK TABLES)."""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Rangos de línea en dump_limpio.sql (1-based, inclusive start, exclusive end)
RANGES: dict[str, tuple[int, int]] = {
    "cultivosestado": (405, 479),
    "ddjj_personas": (479, 585),
}

SKIP = re.compile(r"^(LOCK TABLES|UNLOCK TABLES|/\*!40000 ALTER TABLE)", re.I)


def tidb_fix(sql: str) -> str:
    sql = re.sub(r"DEFAULT CHARSET=utf8mb3\b", "DEFAULT CHARSET=utf8mb4", sql, flags=re.I)
    sql = re.sub(r"CHARACTER SET ucs2[^,\n)]*", "CHARACTER SET utf8mb4", sql, flags=re.I)
    sql = re.sub(r"COLLATE ucs2_general_ci", "COLLATE utf8mb4_unicode_ci", sql, flags=re.I)
    sql = re.sub(
        r"CHARACTER SET latin1 COLLATE latin1_swedish_ci",
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
        sql,
        flags=re.I,
    )
    sql = sql.replace("'0000-00-00'", "'1970-01-01'")
    return sql


def extract_range(dump: Path, start: int, end: int) -> list[str]:
    stmts: list[str] = []
    buf: list[str] = []
    with dump.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            if lineno < start:
                continue
            if lineno >= end:
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            if SKIP.match(stripped):
                continue
            buf.append(line)
            if stripped.endswith(";"):
                stmts.append(tidb_fix("".join(buf)))
                buf.clear()
    return stmts


def main() -> None:
    tables = sys.argv[1:] or list(RANGES.keys())
    dump = ROOT / "dump_limpio.sql"

    import pymysql

    conn = pymysql.connect(
        host=os.environ["TIDB_HOST"],
        port=int(os.environ.get("TIDB_PORT", 4000)),
        user=os.environ["TIDB_USER"],
        password=os.environ["TIDB_PASS"],
        database=os.environ.get("TIDB_DB", "emergencias"),
        charset="utf8mb4",
        ssl={"ca": os.environ.get("TIDB_SSL_CA", "/etc/ssl/cert.pem")},
    )
    try:
        for table in tables:
            if table not in RANGES:
                print(f"ERROR: tabla desconocida {table}", file=sys.stderr)
                continue
            start, end = RANGES[table]
            print(f"\n=== {table} (líneas {start}-{end}) ===")
            stmts = extract_range(dump, start, end)
            print(f"  {len(stmts)} sentencias")
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            conn.commit()
            t0 = time.time()
            for i, sql in enumerate(stmts, 1):
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
                if i == 1:
                    print(f"  CREATE OK ({len(sql)} chars)")
                elif i == 2:
                    print(f"  INSERT en curso ({len(sql)/1e6:.1f} MB)…")
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                n = cur.fetchone()[0]
            print(f"  ✓ {n:,} filas en {time.time()-t0:.0f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
