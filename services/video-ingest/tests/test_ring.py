from app.ring import FrameRing
import pytest
from app.ring import require_evidence_window


def test_evidence_requires_pre_and_post_event_coverage():
    full = [(t / 2, b'frame') for t in range(10, 31)]
    require_evidence_window(full, 10)
    for partial in (full[8:], full[:-8], [], full[::4]):
        with pytest.raises(ValueError):
            require_evidence_window(partial, 10)


def test_default_ring_retains_window_until_encoding_deadline():
    ring = FrameRing()
    for half_second in range(61):
        ring.append(half_second / 2, b'frame')
    require_evidence_window(ring.frames(5, 15), 10)


def test_ring_bounds_age_and_bytes():
    ring = FrameRing(seconds=5, max_bytes=10)
    ring.append(0, b'1111')
    ring.append(1, b'2222')
    ring.append(2, b'3333')
    assert ring.frames() == [(1, b'2222'), (2, b'3333')]
    ring.append(8, b'4444')
    assert ring.frames() == [(8, b'4444')]
    assert ring.size_bytes == 4


def test_ring_rejects_oversize_and_resets_reversed_time():
    ring = FrameRing(seconds=5, max_bytes=4)
    assert not ring.append(1, b'12345')
    ring.append(2, b'12')
    ring.append(1, b'34')
    assert ring.frames() == [(1, b'34')]
