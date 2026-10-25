"""Loop a permitted local clip into the same RTSP path used by live inputs."""
import os
import signal
import subprocess
from pathlib import Path
from threading import Event

stop = Event()
process = None


def shutdown(*_):
    stop.set()
    if process is not None and process.poll() is None:
        process.terminate()


def main():
    global process
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    clip = Path(os.environ["SMARTOPS_LOOP_FILE"])
    if not clip.is_file():
        raise SystemExit("Loop input is missing; mount a permitted video file")
    target = os.environ.get("SMARTOPS_PUBLISH_URL", "rtsp://mediamtx:8554/demo-lobby")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
               "-re", "-stream_loop", "-1", "-i", str(clip), "-an",
               "-vf", "scale=960:-2,fps=15", "-c:v", "libx264",
               "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
               "-g", "15", "-keyint_min", "15", "-sc_threshold", "0", "-bf", "0",
               "-threads", "2", "-f", "rtsp", "-rtsp_transport", "tcp", target]
    while not stop.is_set():
        process = subprocess.Popen(command)
        process.wait()
        if not stop.is_set():
            print("Publisher disconnected; retrying in 2 seconds", flush=True)
            stop.wait(2)


if __name__ == "__main__":
    main()
