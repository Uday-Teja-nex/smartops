"""Loop a permitted local clip into the same RTSP path used by live inputs."""
import os
import signal
import subprocess
import hashlib
import tempfile
from pathlib import Path
from threading import Event

stop = Event()
process = None


def shutdown(*_):
    stop.set()
    for child in [process, *children]:
        if child is not None and child.poll() is None:
            child.terminate()


def run_preparation(command):
    global process
    process = subprocess.Popen(command)
    try:
        code = process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    if code:
        raise subprocess.CalledProcessError(code, command)


def prepare_clip(clip, cache, run=run_preparation):
    # Version the encoding recipe as well as the input contents.
    digest = hashlib.sha256(b'h264-960-15fps-g15-no-bframes-v1')
    with clip.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f'{digest.hexdigest()}.mp4'
    if target.is_file() and target.stat().st_size:
        return target
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.mp4', delete=False) as handle:
        temporary = Path(handle.name)
    try:
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
             '-i', str(clip), '-map', '0:v:0', '-an', '-vf', 'scale=960:-2,fps=15',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
             '-pix_fmt', 'yuv420p', '-g', '15', '-keyint_min', '15',
             '-sc_threshold', '0', '-bf', '0', '-threads', '2', str(temporary)])
        if not temporary.stat().st_size:
            raise RuntimeError('Clip preparation produced no video')
        temporary.replace(target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def load_manifest(path, media_root):
    """Return [(rtsp path, clip)] from a streams.json manifest.

    Each entry is {"path": "mall-store", "file": "first test video.mp4"}.
    Entries whose file is missing are skipped with a log line rather than
    stopping the other streams.
    """
    import json
    entries = json.loads(Path(path).read_text(encoding='utf-8')).get('streams', [])
    streams = []
    for entry in entries:
        name, file = str(entry.get('path', '')).strip(), str(entry.get('file', '')).strip()
        if not name or not file or '/' in name or '..' in file:
            print(f'Skipping invalid manifest entry {entry!r}', flush=True)
            continue
        clip = Path(media_root) / file
        if not clip.is_file():
            print(f'Skipping {name}: {clip} is missing', flush=True)
            continue
        streams.append((name, clip))
    return streams


def publish_forever(clip, target):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
               "-re", "-stream_loop", "-1", "-i", str(clip), "-map", "0:v:0",
               "-an", "-c:v", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", target]
    while not stop.is_set():
        child = subprocess.Popen(command)
        children.append(child)
        child.wait()
        children.remove(child)
        if not stop.is_set():
            print(f"Publisher for {target} disconnected; retrying in 2 seconds", flush=True)
            stop.wait(2)


children = []


def main():
    import threading
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    cache = Path(os.getenv('SMARTOPS_LOOP_CACHE', '/cache'))
    base = os.getenv('SMARTOPS_RTSP_BASE', 'rtsp://mediamtx:8554').rstrip('/')
    manifest = os.getenv('SMARTOPS_STREAM_MANIFEST', '')
    if manifest and Path(manifest).is_file():
        streams = load_manifest(manifest, os.getenv('SMARTOPS_MEDIA_ROOT', '/media'))
    else:
        clip = Path(os.environ.get("SMARTOPS_LOOP_FILE", ""))
        if not clip.is_file():
            raise SystemExit("No stream manifest and no loop input; mount sample-data/streams.json")
        streams = [(os.getenv('SMARTOPS_PUBLISH_PATH', 'demo-lobby'), clip)]
    if not streams:
        print("Manifest lists no available footage; nothing to publish", flush=True)
        stop.wait()
        return
    threads = []
    for name, clip in streams:
        prepared = prepare_clip(clip, cache)
        if stop.is_set():
            return
        print(f"Publishing {clip.name} to {base}/{name}", flush=True)
        thread = threading.Thread(target=publish_forever, args=(prepared, f"{base}/{name}"), daemon=True)
        thread.start()
        threads.append(thread)
    stop.wait()
    for child in list(children):
        if child.poll() is None:
            child.terminate()
    for thread in threads:
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
