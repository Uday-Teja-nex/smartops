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


def test_short_pre_roll_is_accepted_only_right_after_connect():
    import pytest
    from app.ring import require_evidence_window
    frames = [(t / 3, b'x') for t in range(0, 3 * 8)]          # 0 .. 7.67 s, camera started at 0
    require_evidence_window(frames, 2.5, pre_seconds=2.5)        # 2.5 s pre-roll at stream start
    with pytest.raises(ValueError):
        require_evidence_window(frames, 2.5)                     # normal 5 s requirement fails
    with pytest.raises(ValueError):
        require_evidence_window(frames, 0.5, pre_seconds=0.5)    # under 1 s is never accepted


class _Frame:
    def __init__(self, sequence, captured_at, monotonic_at):
        self.image, self.sequence = b'img', sequence
        self.captured_at, self.monotonic_at = captured_at, monotonic_at


class _Reader:
    def __init__(self):
        self.frame = None

    def latest(self):
        return self.frame


def test_sampler_keeps_clip_continuous_while_detection_stalls():
    from app.ring import FrameRing, RingSampler, require_evidence_window

    reader, ring = _Reader(), FrameRing()
    sampler = RingSampler(reader, ring, lambda image: b'jpeg', fps=3)
    # 12 s of camera at 3 fps sampling; nothing else touches the ring, as when
    # every detector call in that period overran its 1.5 s budget.
    for step in range(36):
        t = 1000 + step / 3
        reader.frame = _Frame(step + 1, t, t)
        assert sampler.sample_once(t + .05)
    frames = ring.frames(1006 - 5, 1006 + 5)
    require_evidence_window(frames, 1006, pre_seconds=5.0)
    assert sampler.first_at == 1000
    assert sampler.latest().sequence == 36


def test_sampler_skips_repeated_and_stale_frames():
    from app.ring import FrameRing, RingSampler

    reader, ring = _Reader(), FrameRing()
    sampler = RingSampler(reader, ring, lambda image: b'jpeg', fps=3)
    reader.frame = _Frame(1, 10.0, 10.0)
    assert sampler.sample_once(10.1)
    assert not sampler.sample_once(10.4)  # same frame again
    reader.frame = _Frame(2, 11.0, 11.0)
    assert not sampler.sample_once(13.0)  # camera stalled: no fake continuity
    assert len(ring.frames()) == 1


def test_replace_swaps_annotated_copy_in_place():
    from app.ring import FrameRing

    ring = FrameRing()
    for t in (1.0, 1.33, 1.66):
        ring.append(t, b'plain')
    assert ring.replace(1.33, b'annotated!')
    assert not ring.replace(1.5, b'x')
    assert [jpeg for _, jpeg in ring.frames()] == [b'plain', b'annotated!', b'plain']
    assert ring.size_bytes == len(b'plain') * 2 + len(b'annotated!')
