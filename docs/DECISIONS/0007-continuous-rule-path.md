# ADR 0007: Fresh stream observations precede AI review

Accepted 2026-10-25; implementation and acceptance testing are in progress.

MediaMTX 1.21.2 accepts a looping FFmpeg publisher and real RTSP cameras.
The publisher normalizes the supplied MP4 to H.264, 15 fps and one-second
keyframes. All exposed media ports are loopback-only for this development
slice. Phone/LAN access and authenticated cloud access remain later work.

A separate processor drains decoded RTSP frames on a dedicated thread,
retaining only the latest frame. Detection samples at 3 fps and discards
results older than 1.5 seconds. ByteTrack (Supervision 0.25.1) runs separately
per object class, preventing person/bag identity crossover. Rule observations
use normalized bounding-box bottom centers. Tracking and dwell reset across
observation gaps; frozen/low-light/tamper classifiers are still pending.

Zone rules emit measured count/dwell metadata. Incidents are posted immediately
to the existing idempotent API and SSE path, before any model request. AI and
evidence readiness remain explicit. This first slice is one configured source
per process. SQLite incident retries and an evidence completion journal survive restarts.
Dynamic source/config updates, a bounded pre/post JPEG ring, unattended-object
and schedule rules are implemented. Evidence runs off the detection loop;
missing footage is reported explicitly. Timestamped detections and matching
JPEG previews are sent over authenticated SSE, scoped by observation org.
This sampled preview is labeled honestly; full-rate WebRTC/LL-HLS remains pending.

The engineering test uses a full-frame restricted-entry polygon deliberately
to validate wiring on the supplied clip. Its incidents are engineering test
observations, not evidence of an actual security violation, and must be removed
before building client demo history.

References: [MediaMTX Docker setup](https://github.com/bluenviron/mediamtx/blob/v1.21.2/docs/1-kickoff/2-install.md),
[on-demand publisher example](https://github.com/bluenviron/mediamtx/blob/v1.21.2/docs/2-features/14-on-demand-publishing.md),
[OpenCV capture properties](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html).
ByteTrack's pinned package source/docstrings were inspected locally before use.
