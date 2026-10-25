"""Register an engineering-only full-frame entry zone on the supplied clip loop."""
import json
from pathlib import Path

import httpx

with httpx.Client(base_url='http://localhost:8000', timeout=10) as client:
    login = client.post('/v1/auth/login', json={'email': 'admin@smartops.local', 'password': 'smartops-demo'})
    login.raise_for_status()
    client.headers['Authorization'] = f"Bearer {login.json()['token']}"
    sources = client.get('/v1/sources')
    sources.raise_for_status()
    existing = next((s for s in sources.json() if s['name'] == 'Engineering RTSP rule test'), None)
    payload = {
        'name': 'Engineering RTSP rule test', 'buildingId': 'bldg-north-01',
        'floor': 'L1', 'zone': 'Engineering test area', 'sourceType': 'rtsp',
        'sourceUri': 'rtsp://mediamtx:8554/demo-lobby', 'enabled': True,
        'tags': ['engineering-verification'],
        'positionNotes': 'Full-frame test polygon; verifies mechanics, not a real restricted boundary.',
        'detectionConfig': {'zones': [{'id': 'full-frame-test', 'polygon': [[0,0],[1,0],[1,1],[0,1]],
                                     'rules': [{'type': 'restricted_entry', 'durationSeconds': 0}]}]},
    }
    result = client.patch(f"/v1/sources/{existing['id']}", json=payload) if existing else client.post('/v1/sources', json=payload)
    result.raise_for_status()
    report = {'sourceId': result.json()['id'], 'purpose': 'engineering-only rule pipeline verification'}
    Path('docs/verification/stream-test-source.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
