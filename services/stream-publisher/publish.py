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
    if process is not None and process.poll() is None:
        process.terminate()


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


def main():
    global process
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    clip = Path(os.environ["SMARTOPS_LOOP_FILE"])
    if not clip.is_file():
        raise SystemExit("Loop input is missing; mount a permitted video file")
    clip = prepare_clip(clip, Path(os.getenv('SMARTOPS_LOOP_CACHE', '/cache')))
    if stop.is_set():
        return
    target = os.environ.get("SMARTOPS_PUBLISH_URL", "rtsp://mediamtx:8554/demo-lobby")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
               "-re", "-stream_loop", "-1", "-i", str(clip), "-map", "0:v:0",
               "-an", "-c:v", "copy", "-f", "rtsp", "-rtsp_transport", "tcp", target]
    while not stop.is_set():
        process = subprocess.Popen(command)
        process.wait()
        if not stop.is_set():
            print("Publisher disconnected; retrying in 2 seconds", flush=True)
            stop.wait(2)


if __name__ == "__main__":
    main()
