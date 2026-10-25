from app.ring import FrameRing


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
