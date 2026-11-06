"""Measure actual stream progress and Docker memory; never synthesize incidents."""
import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--minutes', type=float, default=30)
    parser.add_argument('--output', default='docs/verification/stream-soak.json')
    args = parser.parse_args()
    ids = json.loads(Path('docs/verification/soak-sources.json').read_text())['sourceIds']
    report = {'startedAt': datetime.now(UTC).isoformat(), 'requestedMinutes': args.minutes,
              'sourceIds': ids, 'samples': [], 'purpose': 'Capacity test: same supplied clip on three independent RTSP transports'}
    started = time.monotonic()
    with httpx.Client(base_url='http://localhost:8000', timeout=10) as client:
        def sign_in():
            # Access tokens last 15 minutes; a 30-minute soak must re-authenticate.
            response = client.post('/v1/auth/login', json={'email': 'admin@smartops.local', 'password': 'smartops-demo'})
            response.raise_for_status()
            client.headers['Authorization'] = 'Bearer ' + response.json()['token']

        sign_in()
        while True:
            if client.get('/v1/auth/me').status_code == 401:
                sign_in()
            sample = {'elapsedSeconds': round(time.monotonic() - started, 2), 'sources': []}
            for source_id in ids:
                try:
                    response = client.get(f'/v1/sources/{source_id}')
                    response.raise_for_status()
                    source = response.json()
                    row = {'id': source_id, 'status': source['status'], 'health': source['health']}
                    observation = client.get(f'/v1/sources/{source_id}/observations')
                    row['observationStatus'] = observation.status_code
                    if observation.is_success:
                        data = observation.json()
                        row['sequence'] = data['sequence']
                        row['observationAgeSeconds'] = (datetime.now(UTC) - datetime.fromisoformat(data['capturedAt'].replace('Z', '+00:00'))).total_seconds()
                    sample['sources'].append(row)
                except httpx.HTTPError as exc:
                    sample['sources'].append({'id': source_id, 'error': type(exc).__name__})
            stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'], capture_output=True, text=True, timeout=20)
            sample['containers'] = [row for line in stats.stdout.splitlines() if (row := json.loads(line))['Name'].startswith('smartops-')]
            sample['statsExitCode'] = stats.returncode
            report['samples'].append(sample)
            report['elapsedSeconds'] = round(time.monotonic() - started, 2)
            Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps({'elapsedSeconds': report['elapsedSeconds'], 'sources': [
                {'id': s['id'], 'fps': s.get('health', {}).get('processingFps'), 'age': s.get('observationAgeSeconds'), 'error': s.get('error')}
                for s in sample['sources']]}), flush=True)
            if time.monotonic() - started >= args.minutes * 60:
                break
            time.sleep(min(10, max(0, args.minutes * 60 - (time.monotonic() - started))))


if __name__ == '__main__':
    main()
