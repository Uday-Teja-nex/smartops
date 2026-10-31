from app.outbox import Outbox


def test_quarantine_is_durable_and_preserves_newer_pending_update(tmp_path):
    path = tmp_path / 'quarantine.db'
    box = Outbox(path)
    old = {'id': 'one', 'version': 1}
    box.append(old)
    box.append({'id': 'one', 'version': 2})
    box.quarantine(old, 422)
    assert box[0]['version'] == 2
    assert box.delivery_health() == {'pendingIncidents': 1, 'rejectedIncidentVersions': 1, 'pendingReviews': 0}
    box.close()
    box = Outbox(path)
    assert box.db.execute('SELECT id,status FROM dead_letters').fetchall() == [('one', 422)]
    assert box[0]['version'] == 2
    sequence = box.db.execute('SELECT sequence FROM dead_letters').fetchone()[0]
    assert box.replay_dead_letter(sequence) is False
    box.acknowledge(box[0])
    assert box.replay_dead_letter(sequence) is True
    assert box[0]['version'] == 1
    assert box.replay_dead_letter(sequence) is False
    box.close()


def test_unsent_incident_survives_restart_and_upsert_is_idempotent(tmp_path):
    path = tmp_path / 'outbox.db'
    box = Outbox(path)
    box.append({'id': 'inc-one', 'value': 1})
    box.append({'id': 'inc-one', 'value': 2})
    box.close()

    box = Outbox(path)
    assert len(box) == 1
    assert box[0] == {'id': 'inc-one', 'value': 2}
    box.popleft()
    box.close()
    box = Outbox(path)
    assert len(box) == 0
    box.close()


def test_interrupted_evidence_is_reported_after_restart(tmp_path):
    path = tmp_path / 'evidence.db'
    box = Outbox(path)
    box.track_evidence({'id': 'inc-interrupted', 'reviewNotes': []})
    box.track_evidence({'id': 'inc-completed', 'reviewNotes': []})
    box.finish_evidence({'id': 'inc-completed', 'reviewNotes': [], 'evidence': {'clipUrl': '/clip'}})
    box.close()

    box = Outbox(path)
    box.recover_evidence()
    delivered = []
    while box:
        delivered.append(box[0])
        box.popleft()
    assert len(delivered) == 2
    interrupted = next(p for p in delivered if p['id'] == 'inc-interrupted')
    assert interrupted['reviewNotes'] == ['Evidence unavailable: processor restarted before evidence completed']
    assert next(p for p in delivered if p['id'] == 'inc-completed')['evidence']['clipUrl'] == '/clip'
    box.recover_evidence()
    assert not box
    box.close()


def test_acknowledging_old_delivery_does_not_drop_a_newer_update(tmp_path):
    box = Outbox(tmp_path / 'concurrent.db')
    box.append({'id': 'one', 'version': 1})
    sent = box[0]
    box.append({'id': 'one', 'version': 2})
    box.acknowledge(sent)
    assert box[0]['version'] == 2
    box.acknowledge(box[0])
    assert not box
    box.close()
