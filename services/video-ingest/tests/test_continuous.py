from app.continuous import incident_payload


def test_rule_incident_preserves_measurements_without_ai_claims():
    source = {'id': 's1', 'buildingId': 'b1', 'floor': 'L1', 'zone': 'Lobby'}
    event = {'zoneId': 'entry', 'type': 'restricted_entry', 'count': 1,
             'durationSeconds': 0, 'confidence': .85, 'trackIds': [2]}
    payload = incident_payload(source, event, 1000)
    assert payload['modelProvider'] == 'rule-engine'
    assert payload['sourceId'] == 's1'
    assert payload['detectionSummary'] == event
    assert payload['detailedNarrative'] == []
    assert payload['evidence']['clipUrl'] == ''
    assert payload['reviewNotes'] == ['AI review unavailable: enrichment is not configured.']
