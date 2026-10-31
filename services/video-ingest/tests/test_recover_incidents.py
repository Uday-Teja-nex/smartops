import json
import pytest
from app.outbox import Outbox
from app.recover_incidents import main


def test_inspection_hides_payload_and_replay_retains_newer_data(tmp_path, capsys):
    path = tmp_path / 'journal.db'
    box = Outbox(path)
    payload = {'id': 'incident', 'private': 'never-print-this'}
    box.append(payload)
    box.quarantine(payload, 422)
    box.close()
    args = ['--database', str(path)]
    assert main(args + ['list']) == 0
    output = capsys.readouterr().out
    assert 'never-print-this' not in output
    sequence = json.loads(output)[0]['sequence']
    box = Outbox(path)
    box.append({'id': 'incident', 'version': 2})
    box.close()
    assert main(args + ['replay', str(sequence)]) == 1
    box = Outbox(path)
    assert box[0]['version'] == 2
    box.acknowledge(box[0])
    box.close()
    assert main(args + ['replay', str(sequence)]) == 0
    assert 'not yet confirmed' in capsys.readouterr().out
    box = Outbox(path)
    assert box[0] == payload
    box.close()


def test_typo_does_not_create_empty_journal(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(SystemExit):
        main(['--database', str(path), 'list'])
    assert not path.exists()
