# 0010: Explicit free hosted reviews with bounded asynchronous enrichment

Date: 2026-10-29

Local vision inference on this laptop has not met the latency gate. User requested
free hosted models and explicitly authorized provider data collection for selected
incident images. The OpenRouter key authenticates, and a real saved-image request
completed in 4.31 seconds. This does not validate incident accuracy.

Keep continuous object detection and measured zone rules local. Explicitly select
an OpenRouter `:free` vision model with zero catalog input/output price; never
silently substitute paid models or relax privacy routing. Default data collection
is deny; this user's ignored local configuration explicitly selects allow.

The continuous worker records incidents immediately. Evidence completion queues
one saved image in the same durable source journal. A separate worker waits for
delivery acknowledgement before requesting supplemental narrative and operator
actions. Neither model output nor model failure alters rule type, severity,
confidence or lifecycle. Existing API upserts preserve operator lifecycle state.

Each source retains at most 20 pending review images, each at most one million
base64 characters. Automatic reviews share a durable 40-attempt UTC-day budget
across camera journals. Reserve before sending; errors and interrupted attempts
count. No immediate automatic retry after provider failure. A process interrupted
during a request can retry after restart, consuming another reservation. This is
at-least-once review, with idempotent incident updates, not exactly-once inference.
Manual endpoints/probes are outside this worker budget. Account limits remain
authoritative, and free capacity can be unavailable at any time.

Orchestrator host access is loopback-only. Production service authentication,
cross-host quotas, retention policy for journals, richer temporal evidence, and
validated event accuracy remain later gates. Hugging Face CV is opt-in experimental
and not enabled for continuous operation because credits are limited.
