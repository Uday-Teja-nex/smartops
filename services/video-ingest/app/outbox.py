"""Durable, idempotent incident delivery across API outages and process restarts."""
import json
import sqlite3


class Outbox:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS dead_letters (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL, payload TEXT NOT NULL, status INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evidence_jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS review_images (id TEXT PRIMARY KEY, image TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS review_jobs (id TEXT PRIMARY KEY, source TEXT NOT NULL, payload TEXT NOT NULL, image TEXT NOT NULL, claimed INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS review_budget (day TEXT PRIMARY KEY, used INTEGER NOT NULL)')
        self.db.commit()

    def track_evidence(self, payload, image=None):
        with self.db:
            if image is not None:
                queued = self.db.execute('SELECT (SELECT count(*) FROM review_images) + (SELECT count(*) FROM review_jobs)').fetchone()[0]
                if queued < 20 and len(image) <= 1000000:
                    self.db.execute('INSERT OR REPLACE INTO review_images VALUES (?, ?)', (payload['id'], image))
                    payload['reviewNotes'] = ['AI review pending evidence completion.']
                else:
                    payload['reviewNotes'] = ['AI review unavailable: queue capacity reached.']
            self.db.execute('INSERT OR REPLACE INTO evidence_jobs VALUES (?, ?)',
                            (payload['id'], json.dumps(payload)))

    def finish_evidence(self, payload):
        # Delivery and journal removal commit together, including on shutdown.
        with self.db:
            image = self.db.execute('SELECT image FROM review_images WHERE id=?', (payload['id'],)).fetchone()
            if image:
                payload['reviewNotes'] = [note for note in payload.get('reviewNotes', []) if not note.startswith('AI review')]
                payload['reviewNotes'].append('AI review queued; measured rule incident remains active.')
                self.db.execute('INSERT OR IGNORE INTO review_jobs (id,source,payload,image) VALUES (?,?,?,?)',
                                (payload['id'], payload['sourceId'], json.dumps(payload), image[0]))
                self.db.execute('DELETE FROM review_images WHERE id=?', (payload['id'],))
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

    def delivery_health(self):
        row = self.db.execute('SELECT (SELECT count(*) FROM pending), '
                              '(SELECT count(*) FROM dead_letters), '
                              '(SELECT count(*) FROM review_jobs)').fetchone()
        return dict(zip(('pendingIncidents', 'rejectedIncidentVersions', 'pendingReviews'), row))

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

    def quarantine(self, payload, status):
        """Retain the rejected version without deleting a newer concurrent update."""
        raw = json.dumps(payload)
        with self.db:
            self.db.execute('INSERT INTO dead_letters(id,payload,status) VALUES (?,?,?)',
                            (payload['id'], raw, status))
            self.db.execute('DELETE FROM pending WHERE id=? AND payload=?', (payload['id'], raw))

    def close(self):
        self.db.close()

    def replay_dead_letter(self, sequence):
        """Explicit operator recovery; never overwrite a newer pending version."""
        with self.db:
            row = self.db.execute('SELECT id,payload FROM dead_letters WHERE sequence=?', (sequence,)).fetchone()
            if row is None:
                return False
            inserted = self.db.execute('INSERT OR IGNORE INTO pending(id,payload) VALUES (?,?)', row)
            if not inserted.rowcount:
                return False
            self.db.execute('DELETE FROM dead_letters WHERE sequence=?', (sequence,))
            return True
