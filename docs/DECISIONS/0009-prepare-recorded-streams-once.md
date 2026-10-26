# 0009 — Prepare recorded streams once

Date: 2026-10-26

Each prerecorded publisher previously decoded, scaled and encoded its loop
continuously. Three such publishers compete with CPU detection on the demo
laptop. Prepare the same 960-wide, 15 FPS H.264 stream once, then publish with
FFmpeg stream copy. Detector input resolution and event rules are unchanged.

The cache key includes input contents and the encoding recipe version. A
temporary output is atomically renamed only after successful encoding. Failed
or interrupted output is never reused. Preparation has a five-minute timeout;
failure stops the publisher visibly. Shutdown terminates the active encoder.
Cache files live in the publisher container's writable /cache directory and
survive process/container restarts, but not container recreation. The demo
startup workflow must account for first preparation; no startup-time pass is
claimed yet. Future multiple-clip management needs bounded cache retention.

This optimization needs measured runtime confirmation. The preceding soak had
sub-2-FPS intervals and concurrent host/build load; it is not a clean causal
comparison. No performance improvement is asserted from unit tests alone.

Reference: official [FFmpeg stream-copy documentation](https://www.ffmpeg.org/ffmpeg.html).
Stream copy forwards compressed packets without decoding or re-encoding;
preparation is still necessary for the selected codec and keyframe cadence.
