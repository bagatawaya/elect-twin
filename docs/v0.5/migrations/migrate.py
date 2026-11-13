#!/usr/bin/env python3
"""OpenTwin migration runner — stdlib only (Python 3.12+).

Applies pending *.sql migrations in one transaction each against
projects.sqlite3, chmods the file 0600 (private-vault posture), and
creates the sqlite-vec `vec_chunks` virtual table only when the
sqlite-vec Capability Pack is installed and sha256-verified (packs.py).

Usage:
    python3 migrate.py /path/to/projects.sqlite3
    python3 migrate.py /path/to/projects.sqlite3 --enable-vec  # requires pack
"""
import argparse
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATION_FILES = ["0001_v05.sql"]

# Mirrors security/airlock.py posture: the private vault is never group/world readable.
VAULT_MODE = 0o600


def _sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _chmod_vault(db_path: Path) -> None:
    try:
        os.chmod(db_path, VAULT_MODE)
    except OSError as exc:  # Windows ACLs differ; warn, don't die
        print(f"warning: chmod 0600 failed ({exc}); verify ACLs manually", file=sys.stderr)


def applied_versions(db: sqlite3.Connection) -> set[int]:
    db.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')))"
    )
    return {row[0] for row in db.execute("SELECT version FROM schema_migrations")}


def apply_sql(db: sqlite3.Connection, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    db.executescript(sql)
    print(f"applied {sql_path.name}")


def try_enable_vec(db: sqlite3.Connection) -> bool:
    """Create vec_chunks vec0 if the sqlite-vec pack is installed + pinned.

    Returns True when the vec table exists on exit. Never raises: absence
    of the pack is a normal state (FTS5-only fallback).
    """
    row = db.execute(
        "SELECT artifact_sha256 FROM pack_manifest "
        "WHERE pack_name='sqlite-vec' AND enabled=1"
    ).fetchone()
    if not row:
        print("sqlite-vec pack not installed; vec_chunks not created (FTS5-only mode)")
        return False
    try:
        import sqlite_vec  # type: ignore[import-not-found]  # pack-tier optional
        sqlite_vec.load(db)
        db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
            "chunk_id TEXT PRIMARY KEY, embedding float[1024])"
        )
        db.commit()
        print("vec_chunks vec0 ready (sqlite-vec pack verified by packs.py)")
        return True
    except Exception as exc:  # noqa: BLE001 - deliberate degrade, never break startup
        print(f"sqlite-vec unavailable ({exc}); continuing FTS5-only", file=sys.stderr)
        return False


def migrate(db_path: Path, enable_vec: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        done = applied_versions(db)
        for name in MIGRATION_FILES:
            sql_path = MIGRATIONS_DIR / name
            version = int(name.split("_", 1)[0])
            if version in done:
                print(f"skip {name} (already applied)")
                continue
            with db:  # single transaction per migration
                apply_sql(db, sql_path)
        if enable_vec:
            try_enable_vec(db)
        db.commit()
    finally:
        db.close()
    _chmod_vault(db_path)
    print(f"vault ready: {db_path} (mode {oct(VAULT_MODE)})")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path, help="path to projects.sqlite3")
    parser.add_argument("--enable-vec", action="store_true",
                        help="create vec_chunks when sqlite-vec pack is verified")
    args = parser.parse_args(argv)
    migrate(args.db, args.enable_vec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
