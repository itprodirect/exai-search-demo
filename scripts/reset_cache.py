from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete exa_cache.sqlite safely.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    cache_path = repo_root / "exa_cache.sqlite"

    if not cache_path.exists():
        print(f"No cache file found at {cache_path}")
        return 0

    if cache_path.name != "exa_cache.sqlite":
        raise RuntimeError(f"Refusing to delete unexpected file: {cache_path}")

    # Quick sanity check that it is an SQLite DB before deleting.
    try:
        with sqlite3.connect(cache_path) as conn:
            conn.execute("PRAGMA schema_version;").fetchone()
    except sqlite3.Error as exc:
        print(f"Warning: {cache_path} did not open cleanly as sqlite ({exc}).")
        print("Refusing to delete automatically.")
        return 1

    if not args.yes:
        answer = input(f"Delete {cache_path.name}? Type 'yes' to confirm: ").strip().lower()
        if answer != "yes":
            print("Cancelled.")
            return 0

    cache_path.unlink()
    print(f"Deleted {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
