"""Check real RTSP frames, publisher outage and recovery without fabricated video."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/video-ingest'))
from app.adapters.rtsp import StreamReader


def wait_frame(reader, after=0, timeout=20):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        frame = reader.latest()
        if frame is not None and frame.sequence > after and time.monotonic() - frame.monotonic_at < 1:
            return frame, time.monotonic() - start
        time.sleep(.1)
    raise RuntimeError(reader.last_error or 'No fresh RTSP frame')


def publisher(action):
    subprocess.run(['docker', 'compose', action, 'stream-publisher'],
                   cwd=ROOT, check=True, timeout=30, capture_output=True)


reader = StreamReader('rtsp://127.0.0.1:8554/demo-lobby').start()
try:
    first, startup = wait_frame(reader)
    publisher('stop')
    time.sleep(5)
    stale = reader.latest()
    assert time.monotonic() - stale.monotonic_at > 2
    publisher('start')
    recovered, recovery = wait_frame(reader, after=stale.sequence)
    report = {'firstFrameSeconds': round(startup, 3), 'recoverySeconds': round(recovery, 3),
              'sequenceAdvanced': recovered.sequence > first.sequence,
              'shape': list(recovered.image.shape), 'outageDetected': True}
    (ROOT / 'docs/verification/rtsp-recovery.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
finally:
    publisher('start')
    reader.close()
