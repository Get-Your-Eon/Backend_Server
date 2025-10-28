#!/usr/bin/env python3
"""
Scan and optionally delete Redis keys matching a pattern.
Default pattern targets the coordinate-based station cache keys:
  stations:lat{lat_round}:lon{lon_round}:r{radius}

Usage:
  # dry-run (default) - list keys only
  REDIS_HOST=red-d3kkesh5pdvs739ka080 REDIS_PORT=6379 python3 scripts/clear_redis_cache.py --pattern "stations:lat37.4073*"

  # actually delete found keys (careful)
  REDIS_HOST=red-d3kkesh5pdvs739ka080 REDIS_PORT=6379 python3 scripts/clear_redis_cache.py --pattern "stations:lat37.4073*" --delete

If REDIS_PASSWORD is set, it will be used.
"""

import os
import argparse
import redis


def parse_args():
    p = argparse.ArgumentParser(description="Scan and optionally delete Redis keys for station cache")
    p.add_argument("--pattern", default="stations:lat*", help="Redis SCAN pattern to match keys")
    p.add_argument("--delete", action="store_true", help="Delete matched keys (use with caution)")
    p.add_argument("--count", type=int, default=100, help="SCAN count hint")
    return p.parse_args()


def main():
    args = parse_args()

    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", 6379))
    password = os.environ.get("REDIS_PASSWORD") or None

    print(f"Connecting to Redis {host}:{port} (password set: {'yes' if password else 'no'})")
    try:
        r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"ERROR: cannot connect to Redis: {e}")
        return 2

    pattern = args.pattern
    print(f"Scanning keys with pattern: {pattern}")

    found = []
    try:
        for key in r.scan_iter(match=pattern, count=args.count):
            found.append(key)
    except Exception as e:
        print(f"ERROR while scanning: {e}")
        return 3

    if not found:
        print("No matching keys found.")
        return 0

    print(f"Found {len(found)} key(s):")
    for k in found:
        print("  ", k)

    if args.delete:
        print("Deleting keys...")
        deleted = 0
        for k in found:
            try:
                res = r.delete(k)
                deleted += res
                print(f"Deleted: {k} (result={res})")
            except Exception as e:
                print(f"Failed to delete {k}: {e}")
        print(f"Deleted {deleted} keys (requested {len(found)})")
    else:
        print("Dry-run: no keys were deleted. Re-run with --delete to remove them.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
