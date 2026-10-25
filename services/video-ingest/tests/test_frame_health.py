import numpy as np

from app.frame_health import FrameHealth


def test_no_frames_becomes_offline_and_recovers():
    monitor = FrameHealth(duration=2, freeze_duration=3)
    assert monitor.update(0, None)['issues'] == []
    assert monitor.update(2, None)['issues'] == ['camera_offline']
    image = np.random.default_rng(1).integers(30, 220, (40, 60, 3), dtype=np.uint8)
    assert monitor.update(3, image)['issues'] == []


def test_uniform_dark_and_unchanged_frames_are_measurements_not_tamper_claims():
    monitor = FrameHealth(duration=2, freeze_duration=3)
    dark = np.zeros((40, 60, 3), dtype=np.uint8)
    monitor.update(0, dark)
    monitor.update(1, dark)
    result = monitor.update(2, dark)
    assert set(result['issues']) == {'camera_low_light', 'camera_obscured'}
    assert result['meanLuminance'] == 0
    # Freeze is tracked separately, with an explicitly longer persistence gate.
    assert 'camera_frozen' in monitor.update(3, dark)['issues']
    moving = np.random.default_rng(2).integers(30, 220, (40, 60, 3), dtype=np.uint8)
    assert monitor.update(4, moving)['issues'] == []


def test_capture_gap_does_not_count_toward_frame_condition_dwell():
    monitor = FrameHealth(duration=2, freeze_duration=3)
    dark = np.zeros((40, 60, 3), dtype=np.uint8)
    monitor.update(0, dark)
    assert monitor.update(10, dark)['issues'] == []
