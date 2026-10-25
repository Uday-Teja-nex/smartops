"""Class-separated ByteTrack state with normalized foot-point observations."""
import numpy as np
import supervision as sv

from app.rules import Observation


class Tracker:
    def __init__(self, fps=3):
        self.fps = fps
        self.trackers = {}
        self.previous_time = None
        self.generation = 0
        self.identities = {}
        self.next_id = 1

    def update(self, detections: list[dict], now: float) -> list[Observation]:
        if self.previous_time is not None and (now - self.previous_time > 1.5 or now < self.previous_time):
            self.trackers.clear()
            self.identities.clear()
            self.generation += 1
        self.previous_time = now
        labels = {d['label'] for d in detections} | self.trackers.keys()
        observations = []
        for label in labels:
            if label not in self.trackers:
                self.trackers[label] = sv.ByteTrack(frame_rate=self.fps)
            tracker = self.trackers[label]
            rows = [d for d in detections if d['label'] == label]
            # ByteTrack's Kalman noise model expects pixel-scale coordinates.
            boxes = np.asarray([[d['bbox']['x'] * 1000, d['bbox']['y'] * 1000,
                                 (d['bbox']['x'] + d['bbox']['w']) * 1000,
                                 (d['bbox']['y'] + d['bbox']['h']) * 1000] for d in rows],
                               dtype=np.float32).reshape(-1, 4)
            tracked = tracker.update_with_detections(sv.Detections(
                xyxy=boxes, confidence=np.asarray([d['confidence'] for d in rows], dtype=np.float32)))
            # Supervision retains removed tracks; bound that diagnostic history.
            tracker.removed_tracks = tracker.removed_tracks[-100:]
            for box, confidence, identity in zip(tracked.xyxy, tracked.confidence, tracked.tracker_id):
                key = (label, int(identity))
                if key not in self.identities:
                    self.identities[key] = self.next_id
                    self.next_id += 1
                observations.append(Observation(self.identities[key], label,
                                                float(np.clip((box[0] + box[2]) / 2000, 0, 1)),
                                                float(np.clip(box[3] / 1000, 0, 1)), float(confidence)))
            active_ids = {int(t.external_track_id) for t in tracker.tracked_tracks + tracker.lost_tracks}
            self.identities = {key: value for key, value in self.identities.items()
                               if key[0] != label or key[1] in active_ids}
        return observations
