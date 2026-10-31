# Recover rejected incident deliveries

The continuous processor keeps a SQLite journal per source under `/data`.
Its filename is the SHA-256 hex digest of the source ID, followed by `.db`.
Rejected HTTP requests remain in `dead_letters`; their payloads are not lost.
Fix the rejection's cause before replaying. A 422 generally means invalid data;
replaying it unchanged will reject it again. Never replay every record blindly.

Run the recovery module inside the processor container or from its service
directory with the project's Python environment. Replace the example path
with the existing journal path. The module does not create missing journals.

```powershell
python -m app.recover_incidents --database /data/SOURCE_SHA256.db list --limit 50
```

The read-only listing prints sequence, incident ID, HTTP status and UTC rejection
time. It excludes payloads, images and credentials. Use the sequence to request
one replay:

```powershell
python -m app.recover_incidents --database /data/SOURCE_SHA256.db replay 1
```

Replay atomically moves that rejected version into pending delivery. It refuses
to overwrite an incident that already has a pending update. Exit code 0 means
queued, not delivered; confirm the `rule_incident_persisted` log and API record.
Exit code 1 means no replay or a database error; argument errors use exit code 2.
Reviews remain held if other rejected versions of the same incident still exist.

Local tests cover inspection privacy, restart persistence and concurrent pending
updates. Container execution and real API recovery remain unverified.
