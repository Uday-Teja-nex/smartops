"""Durable, idempotent incident delivery across API outages and process restarts."""
import json
import sqlite3


class Outbox:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evidence_jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.commit()

    def track_evidence(self, payload):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO evidence_jobs VALUES (?, ?)',
                            (payload['id'], json.dumps(payload)))

    def finish_evidence(self, payload):
        # Delivery and journal removal commit together, including on shutdown.
        with self.db:
            self.db.execute('INSERT INTO pending VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                            (payload['id'], json.dumps(payload)))
            self.db.execute('DELETE FROM evidence_jobs WHERE id=?', (payload['id'],))

    def recover_evidence(self):
        for (raw,) in self.db.execute('SELECT payload FROM evidence_jobs').fetchall():
            payload = json.loads(raw)
            payload.setdefault('reviewNotes', []).append(
                'Evidence unavailable: processor restarted before evidence completed')
            self.finish_evidence(payload)

    def append(self, payload):
        with self.db:
            self.db.execute('INSERT INTO pending(id,payload) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                            (payload['id'], json.dumps(payload)))

    def __len__(self):
        return self.db.execute('SELECT count(*) FROM pending').fetchone()[0]

    def __getitem__(self, index):
        if index != 0:
            raise IndexError('Only the oldest pending incident can be read')
        row = self.db.execute('SELECT payload FROM pending ORDER BY rowid LIMIT 1').fetchone()
        if row is None:
            raise IndexError('Outbox is empty')
        return json.loads(row[0])

    def popleft(self):
        with self.db:
            self.db.execute('DELETE FROM pending WHERE rowid=(SELECT rowid FROM pending ORDER BY rowid LIMIT 1)')

    def acknowledge(self, payload):
        with self.db:
            self.db.execute('DELETE FROM pending WHERE id=? AND payload=?',
                            (payload['id'], json.dumps(payload)))

    def close(self):
        self.db.close()
