"""Persistent image-quality measurements; they do not establish intent or cause."""
import cv2
import numpy as np


class FrameHealth:
    def __init__(self, duration=5, freeze_duration=10):
        self.duration = duration
        self.freeze_duration = freeze_duration
        self.previous = None
        self.previous_time = None
        self.since = {}

    def update(self, now, image):
        if self.previous_time is not None and (now < self.previous_time or now - self.previous_time > 1.5):
            self.since = {key: value for key, value in self.since.items() if key == 'camera_offline'}
            self.previous = None
        self.previous_time = now
        measurements = {}
        conditions = {'camera_offline': image is None}
        if image is not None:
            gray = cv2.cvtColor(cv2.resize(image, (64, 36)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            mean, deviation = float(gray.mean()), float(gray.std())
            difference = float(np.abs(gray - self.previous).mean()) if self.previous is not None else None
            measurements = {'meanLuminance': mean, 'luminanceDeviation': deviation,
                            'meanFrameDifference': difference}
            conditions.update(camera_low_light=mean < 25,
                              camera_obscured=deviation < 2,
                              camera_frozen=difference is not None and difference < .1)
            # A stable scene is only a possible freeze. Never claim deliberate tampering.
            if self.previous is None:
                self.since['camera_frozen'] = now
            self.previous = gray
        else:
            self.previous = None
        issues = []
        for kind in ('camera_offline', 'camera_low_light', 'camera_obscured', 'camera_frozen'):
            if conditions.get(kind):
                self.since.setdefault(kind, now)
                threshold = self.freeze_duration if kind == 'camera_frozen' else self.duration
                if now - self.since[kind] >= threshold:
                    issues.append(kind)
            elif not (kind == 'camera_frozen' and image is not None and measurements.get('meanFrameDifference') is None):
                self.since.pop(kind, None)
        return {'issues': issues, **measurements}
