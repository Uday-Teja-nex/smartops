from threading import Event
import pytest
import cv2

import numpy as np

from app.adapters.rtsp import RtspAdapter, StreamReader


def test_decoder_budget_is_passed_at_open(monkeypatch):
    from app.adapters.rtsp import open_capture
    calls = []
    monkeypatch.setenv('SMARTOPS_RTSP_DECODE_THREADS', '2')
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: calls.append(args))
    open_capture('rtsp://camera/live')
    parameters = dict(zip(calls[0][2][::2], calls[0][2][1::2]))
    assert parameters[cv2.CAP_PROP_N_THREADS] == 2
    assert parameters[cv2.CAP_PROP_READ_TIMEOUT_MSEC] == 3000


@pytest.mark.parametrize('value', ['0', '17', 'invalid'])
def test_invalid_decoder_budget_fails_before_open(monkeypatch, value):
    from app.adapters.rtsp import open_capture
    monkeypatch.setenv('SMARTOPS_RTSP_DECODE_THREADS', value)
    monkeypatch.setattr(cv2, 'VideoCapture', lambda *args: pytest.fail('must not open'))
    with pytest.raises(ValueError):
        open_capture('rtsp://camera/live')


class Capture:
    def __init__(self, frames, opened=True):
        self.frames = iter(frames)
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        return next(self.frames, (False, None))

    def release(self):
        self.released = True


def test_probe_requires_decoded_frame(monkeypatch):
    capture = Capture([(False, None)])
    monkeypatch.setattr('app.adapters.rtsp.open_capture', lambda uri: capture)
    result = RtspAdapter({'sourceUri': 'rtsp://camera/live'}).probe()
    assert not result.ok
    assert capture.released


def test_reader_reconnects_and_keeps_only_latest_frame():
    stop = Event()
    captures = []
    def factory(uri):
        if captures:
            stop.set()
            return Capture([], opened=False)
        capture = Capture([(True, np.full((2, 2, 3), i, dtype=np.uint8)) for i in range(20)])
        captures.append(capture)
        return capture

    reader = StreamReader('rtsp://camera/live', stop=stop, capture_factory=factory,
                          retry_initial=0, retry_max=0)
    reader.run()
    assert reader.sequence == 20
    assert reader.latest().image[0, 0, 0] == 19
    assert captures[0].released
    assert reader.last_error is not None


def test_source_credentials_are_not_in_probe_error(monkeypatch):
    def fail(uri):
        raise RuntimeError(uri)
    monkeypatch.setattr('app.adapters.rtsp.open_capture', fail)
    result = RtspAdapter({'sourceUri': 'rtsp://user:secret@camera/live'}).probe()
    assert not result.ok
    assert 'secret' not in result.error
