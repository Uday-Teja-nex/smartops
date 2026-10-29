"""Text-only free model contract probe; never prints credentials or response bodies."""
import json
import argparse
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/orchestrator'))
from app.providers.openai_compatible import OpenAICompatibleProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--data-collection', choices=['deny', 'allow'], default='deny',
                        help='Policy for this synthetic probe only; does not change application settings')
    args = parser.parse_args()
    config = dotenv_values(args.env_file)
    key = config.get('SMARTOPS_MODEL_API_KEY')
    if not key:
        print('Missing SMARTOPS_MODEL_API_KEY in .env')
        return 1
    model = 'nvidia/nemotron-3.5-super-vl:free'
    report = {'model': model, 'data_collection': args.data_collection, 'input': 'synthetic text only'}
    start = time.monotonic()
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get('https://openrouter.ai/api/v1/models')
            response.raise_for_status()
            models = response.json()['data']
        candidate = next((item for item in models if item['id'] == model), None)
        if candidate is None or any(float(candidate['pricing'][field]) != 0 for field in ('prompt', 'completion')):
            raise ValueError('Free candidate unavailable')
        provider = OpenAICompatibleProvider('https://openrouter.ai/api/v1', key, model, model,
                                           timeout_seconds=30, free_only=True, data_collection=args.data_collection)
        result = provider.summarize_incident(
            'Connection test. Return exactly a JSON object with status equal to ok.',
            {'type': 'object', 'properties': {'status': {'type': 'string', 'enum': ['ok']}},
             'required': ['status'], 'additionalProperties': False})
        report['passed'] = result == {'status': 'ok'}
    except httpx.HTTPStatusError as exc:
        report.update(passed=False, error='HTTP error', http_status=exc.response.status_code)
        # Only the error code is retained, never upstream messages or headers.
        try:
            code = exc.response.json().get('error', {}).get('code')
            if isinstance(code, int):
                report['provider_error_code'] = code
        except (ValueError, AttributeError):
            pass
    except Exception as exc:
        report.update(passed=False, error=type(exc).__name__)
    report['elapsed_seconds'] = round(time.monotonic() - start, 2)
    destination = ROOT / 'docs/verification/openrouter-connection.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
