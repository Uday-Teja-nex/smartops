import pytest
from app.tracking import Tracker


def detection(x, label='person'):
    return {'label': label, 'confidence': .9, 'bbox': {'x': x, 'y': .2, 'w': .15, 'h': .5}}


def test_tracking_preserves_id_and_does_not_output_lost_people():
    tracker = Tracker(fps=3)
    first = tracker.update([detection(.2)], 0)
    second = tracker.update([detection(.21)], .33)
    assert first[0].track_id == second[0].track_id
    assert second[0].y == pytest.approx(.7)
    assert tracker.update([], .66) == []


def test_tracking_resets_after_transport_gap():
    tracker = Tracker(fps=3)
    tracker.update([detection(.2)], 0)
    tracker.update([detection(.21)], 30)
    assert tracker.generation == 1
