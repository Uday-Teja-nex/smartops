"""JPEG frame ring bounded by time and bytes, independent of stream duration."""
from collections import deque


class FrameRing:
    def __init__(self, seconds=12, max_bytes=16 * 1024 * 1024):
        if seconds <= 0 or max_bytes <= 0:
            raise ValueError('Ring limits must be positive')
        self.seconds = seconds
        self.max_bytes = max_bytes
        self.size_bytes = 0
        self._frames = deque()

    def append(self, timestamp: float, jpeg: bytes) -> bool:
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

    def frames(self, start=float('-inf'), end=float('inf')):
        return [(timestamp, jpeg) for timestamp, jpeg in self._frames if start <= timestamp <= end]
