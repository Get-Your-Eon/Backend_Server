"""
Find and optionally fix duplicate stations by cs_id in the `stations` table.

Usage:
  PYTHONPATH=. python3 scripts/find_fix_duplicate_stations.py         # list duplicates (dry-run)
  PYTHONPATH=. python3 scripts/find_fix_duplicate_stations.py --fix  # actually delete duplicates (keep newest)

Notes:
- This script uses the DATABASE_URL from `app.core.config.settings`.
- It will not run destructive DELETE unless --fix is provided.
- Always take a DB backup before running --fix. Example:
    pg_dump --dbname="$DATABASE_URL" -Fc -f /tmp/full_backup_before_fix.dump
"""

import argparse
import json
from sqlalchemy import create_engine, text
from app.core.config import settings


def list_duplicates(conn):
    q = "SELECT cs_id, COUNT(*) as cnt FROM stations GROUP BY cs_id HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT 200"
    res = conn.execute(text(q))
    rows = res.fetchall()
    return [(r[0], int(r[1])) for r in rows]


def show_rows_for_cs(conn, csid):
    q = "SELECT *, COALESCE(stat_update_datetime, updated_at) as last_ts FROM stations WHERE cs_id = :csid ORDER BY last_ts DESC NULLS LAST"
    res = conn.execute(text(q), {"csid": csid})
    rows = res.fetchall()
    return rows


def delete_duplicate_keep_newest(conn):
    # Postgres-specific ctid-based approach: rank rows by cs_id and keep rn=1
    delete_sql = """
    WITH ranked AS (
      SELECT ctid, ROW_NUMBER() OVER (PARTITION BY cs_id ORDER BY COALESCE(stat_update_datetime, updated_at) DESC) AS rn
      FROM stations
    )
    DELETE FROM stations WHERE ctid IN (SELECT ctid FROM ranked WHERE rn > 1);
    """
    res = conn.execute(text(delete_sql))
    return res.rowcount if hasattr(res, 'rowcount') else None


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--fix', action='store_true', help='Run destructive delete to remove duplicates (keep newest)')
    args = p.parse_args()

    db_url = settings.DATABASE_URL
    if not db_url:
        print(json.dumps({"error": "DATABASE_URL not set in settings"}, ensure_ascii=False))
        raise SystemExit(1)

    print(f"Using DB: {db_url}")

    engine = create_engine(db_url, future=True)
    try:
        with engine.connect() as conn:
            dups = list_duplicates(conn)
            if not dups:
                print("No duplicate cs_id rows found in stations table.")
                raise SystemExit(0)

            print(f"Found {len(dups)} duplicated cs_id(s). Showing up to 20:")
            for csid, cnt in dups[:20]:
                print(f"- {csid}: {cnt} rows")
                rows = show_rows_for_cs(conn, csid)
                for r in rows:
                    # r is a Row object; convert to dict for compact print
                    try:
                        d = dict(r._mapping)
                    except Exception:
                        d = tuple(r)
                    print("   ", json.dumps(d, default=str, ensure_ascii=False))

            if args.fix:
                print("\n-- Running deletion to remove duplicate rows (keeping newest by stat_update_datetime/updated_at)")
                # confirm
                confirm = input("Type DELETE to proceed: ")
                if confirm.strip() != 'DELETE':
                    print("Aborted by user.")
                    raise SystemExit(1)

                with conn.begin():
                    deleted = delete_duplicate_keep_newest(conn)
                print(f"Deleted rows: {deleted}")
            else:
                print("\nDry-run complete. To remove duplicates, run with --fix after taking a DB backup.")

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        raise
