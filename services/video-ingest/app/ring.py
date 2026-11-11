"""JPEG frame ring bounded by time and bytes, independent of stream duration.

Thread-safe: a sampler thread appends every new camera frame while the
detection loop swaps in annotated versions and copies evidence windows out.
"""
import threading
import time
from collections import deque


def require_evidence_window(frames, triggered_at, tolerance=.75, pre_seconds=5.0):
    """Require pre_seconds before (5 s normally; less only right after the camera
    connected, never under 1 s) and five seconds after, allowing one sampling
    interval of tolerance."""
    if pre_seconds < 1:
        raise ValueError('Incomplete pre/post-event footage')
    if len(frames) < 2 or frames[0][0] > triggered_at - pre_seconds + tolerance or frames[-1][0] < triggered_at + 5 - tolerance:
        raise ValueError('Incomplete pre/post-event footage')
    if any(b[0] - a[0] > 1.5 or b[0] <= a[0] for a, b in zip(frames, frames[1:])):
        raise ValueError('Evidence capture gap')


class FrameRing:
    def __init__(self, seconds=32, max_bytes=16 * 1024 * 1024):
        if seconds <= 0 or max_bytes <= 0:
            raise ValueError('Ring limits must be positive')
        self.seconds = seconds
        self.max_bytes = max_bytes
        self.size_bytes = 0
        self._frames = deque()
        self._lock = threading.Lock()

    def append(self, timestamp: float, jpeg: bytes) -> bool:
        with self._lock:
            return self._append(timestamp, jpeg)

    def _append(self, timestamp: float, jpeg: bytes) -> bool:
        if self._frames and timestamp < self._frames[-1][0]:
            self._frames.clear()
            self.size_bytes = 0
        if len(jpeg) > self.max_bytes:
            return False
        self._frames.append((timestamp, jpeg))
        self.size_bytes += len(jpeg)
        while self._frames and (self._frames[0][0] < timestamp - self.seconds or self.size_bytes > self.max_bytes):
            self.size_bytes -= len(self._frames.popleft()[1])
        return True

    def replace(self, timestamp: float, jpeg: bytes) -> bool:
        """Swap the frame captured at `timestamp` (e.g. for its annotated copy)."""
        with self._lock:
            for index in range(len(self._frames) - 1, -1, -1):
                stamp, old = self._frames[index]
                if stamp == timestamp:
                    self._frames[index] = (stamp, jpeg)
                    self.size_bytes += len(jpeg) - len(old)
                    return True
                if stamp < timestamp:
                    break
            return False

    def frames(self, start=float('-inf'), end=float('inf')):
        with self._lock:
            return [(timestamp, jpeg) for timestamp, jpeg in self._frames if start <= timestamp <= end]


class RingSampler:
    """Feed a FrameRing from a StreamReader at a fixed rate on its own thread.

    Evidence continuity must not depend on detector latency: the detection
    loop blocks on a shared detector, so frames it skips would otherwise leave
    holes in the clip. `first_at` is the capture time of the first sampled frame.
    """

    def __init__(self, reader, ring, encode, *, fps=3, stop=None, max_age=1.5):
        self.reader, self.ring, self.encode = reader, ring, encode
        self.interval = 1 / fps
        self.max_age = max_age
        self.stop = stop if stop is not None else threading.Event()
        self.first_at = None
        self._sequence = 0
        self._latest = None
        self._thread = None

    def latest(self):
        """The last frame put in the ring; the detection loop processes these so
        its annotated copies can replace the same ring entries."""
        return self._latest

    def sample_once(self, now_monotonic=None):
        frame = self.reader.latest()
        now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
        if frame is None or frame.sequence == self._sequence or now_monotonic - frame.monotonic_at > self.max_age:
            return False
        self._sequence = frame.sequence
        jpeg = self.encode(frame.image)
        if jpeg is None or not self.ring.append(frame.captured_at, jpeg):
            return False
        if self.first_at is None:
            self.first_at = frame.captured_at
        self._latest = frame
        return True

    def run(self):
        while not self.stop.is_set():
            started = time.monotonic()
            try:
                self.sample_once(started)
            except Exception:  # noqa: BLE001 - one bad frame must not end sampling
                pass
            self.stop.wait(max(0.0, self.interval - (time.monotonic() - started)))

    def start(self):
        self._thread = threading.Thread(target=self.run, daemon=True, name='ring-sampler')
        self._thread.start()
        return self

    def close(self):
        self.stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
