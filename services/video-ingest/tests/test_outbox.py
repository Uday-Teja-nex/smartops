from app.outbox import Outbox


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
