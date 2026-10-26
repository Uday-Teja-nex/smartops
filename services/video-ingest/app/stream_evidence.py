"""Encode and upload recorded stream frames outside the detection loop."""
import io
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from minio import Minio
from urllib3 import PoolManager, Timeout
from app.ring import require_evidence_window


def upload_evidence(source_id, incident_id, frames, snapshot, detections, triggered_at):
    require_evidence_window(frames, triggered_at)
    endpoint = urlparse(os.getenv('SMARTOPS_MINIO_ENDPOINT', 'http://minio:9000'))
    storage = Minio(endpoint.netloc, access_key=os.getenv('SMARTOPS_MINIO_ACCESS_KEY', 'smartops'),
                    secret_key=os.getenv('SMARTOPS_MINIO_SECRET_KEY', 'smartopsminio'),
                    secure=endpoint.scheme == 'https',
                    http_client=PoolManager(timeout=Timeout(connect=3, read=10), retries=False))
    bucket = os.getenv('SMARTOPS_MINIO_BUCKET', 'smartops-evidence')
    if not storage.bucket_exists(bucket):
        storage.make_bucket(bucket)
    with httpx.Client(base_url=os.getenv('SMARTOPS_API_BASE_URL', 'http://api:8000'), timeout=10,
                      headers={'X-Internal-Token': os.environ['SMARTOPS_INTERNAL_TOKEN']}) as client:
        def save(kind, data, content_type, meta, duration=None):
            suffix = 'mp4' if kind == 'clip' else 'jpg'
            key = f'streams/{source_id}/{incident_id}/{kind}.{suffix}'
            storage.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)
            response = client.post('/v1/evidence', json={
                'sourceId': source_id, 'incidentId': incident_id, 'kind': kind,
                'objectKey': key, 'contentType': content_type, 'sizeBytes': len(data),
                'restricted': True, 'meta': meta, 'durationSeconds': duration,
            })
            response.raise_for_status()
            return response.json()['id']

        snapshot_id = save('snapshot', snapshot, 'image/jpeg', {'detections': detections, 'overlaysBurnedIn': True})
        if len(frames) < 2:
            raise RuntimeError('Insufficient recorded frames for an evidence clip')
        gaps = [b[0] - a[0] for a, b in zip(frames, frames[1:])]
        if max(gaps) > 1.5:
            raise RuntimeError('Evidence clip has a capture gap; refusing to fill missing footage')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lines = []
            for index, (_, jpeg) in enumerate(frames):
                name = f'frame-{index:04d}.jpg'
                (root / name).write_bytes(jpeg)
                lines.append(f"file '{name}'")
                if index < len(gaps):
                    lines.append(f'duration {gaps[index]:.6f}')
            (root / 'frames.txt').write_text('\n'.join(lines), encoding='utf-8')
            subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'concat', '-safe', '1',
                            '-i', str(root / 'frames.txt'), '-c:v', 'libx264', '-preset', 'veryfast',
                            '-pix_fmt', 'yuv420p', '-vf', 'scale=640:-2', '-movflags', '+faststart',
                            '-threads', '2', str(root / 'clip.mp4')], check=True, timeout=30,
                           capture_output=True)
            clip_id = save('clip', (root / 'clip.mp4').read_bytes(), 'video/mp4',
                 {'captureStart': frames[0][0], 'captureEnd': frames[-1][0], 'sampledFrames': len(frames), 'overlaysBurnedIn': True},
                 frames[-1][0] - frames[0][0])
            return {'thumbnailUrl': f'/v1/evidence/{snapshot_id}/url',
                    'clipUrl': f'/v1/evidence/{clip_id}/url', 'restricted': True}
