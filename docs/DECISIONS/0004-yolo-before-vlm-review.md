# ADR 0004: YOLO detection before VLM review

**Status**: accepted

## Context
VLM review is the most expensive step (seconds-to-minutes per call
locally). Sending every sampled window to the VLM wastes compute and, with
hosted providers later, money. Operators also need spatial evidence
(bounding boxes), which chat-style VLM output does not provide reliably.

## Decision
A dedicated detector service runs YOLOv8n on sampled frames first.
Detections are persisted (normalized bboxes, labels, confidence, frame ts)
and gate the pipeline: empty windows are dropped; crowds/object hints go to
the VLM with detection context in the prompt. The detector backend is
pluggable (`ultralytics-cpu` now; ONNX/OpenVINO/CUDA/remote named for
later). If the detector is down, candidates route to human review — never
silently dropped, never faked.

## Consequences
- VLM calls drop by roughly an order of magnitude on quiet footage.
- The UI evidence player gets real, persisted overlays.
- Cost: torch CPU makes the detector image the largest in the stack.
