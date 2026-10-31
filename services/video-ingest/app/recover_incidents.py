"""Inspect rejected deliveries and explicitly replay one after fixing its cause."""
import argparse
import json
from pathlib import Path
import sqlite3

from app.outbox import Outbox


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path, help='Existing per-source SQLite journal')
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('list', help='Show IDs, HTTP status and timestamps; never payloads')
    listing.add_argument('--limit', type=int, default=50)
    replay = commands.add_parser('replay', help='Move one rejected version back to pending delivery')
    replay.add_argument('sequence', type=int)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error('Database must be an existing file; no journal was created')
    if args.command == 'list' and not 1 <= args.limit <= 500:
        parser.error('--limit must be between 1 and 500')
    if args.command == 'replay' and args.sequence < 1:
        parser.error('sequence must be positive')
    try:
        path = args.database.resolve()
        if args.command == 'list':
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            try:
                rows = connection.execute(
                    'SELECT sequence,id,status,created_at FROM dead_letters ORDER BY sequence LIMIT ?',
                    (args.limit,),
                ).fetchall()
                print(json.dumps([dict(zip(('sequence', 'incidentId', 'httpStatus', 'rejectedAt'), row))
                                  for row in rows]))
            finally:
                connection.close()
            return 0
        box = Outbox(path)
        try:
            moved = box.replay_dead_letter(args.sequence)
        finally:
            box.close()
        if not moved:
            print('Not replayed: record is missing or the incident already has a pending update.')
            return 1
        print('Queued for retry. Delivery is not yet confirmed.')
        return 0
    except sqlite3.Error:
        print('Recovery failed: journal is unavailable, locked, or has an unsupported schema.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
