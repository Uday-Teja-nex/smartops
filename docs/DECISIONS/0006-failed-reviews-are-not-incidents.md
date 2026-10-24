# ADR 0006: Failed reviews are telemetry, not incidents

Accepted, 2026-10-24.

The audit found that missing frames, unavailable detection and invalid or failed
VLM responses all produced invented Safety incidents with 35% confidence.
Until the continuous rule engine is in place, these candidates produce no
incident. The worker records `review_unavailable` and the actual reason in
pipeline status. A validated low-confidence model observation can still be
routed to human review; the system must not invent an observation on failure.

Model summary failures preserve actual observations and leave recommendations
empty, with a failure note. Catalog prose must not masquerade as model output.

Phase 2 will persist deterministic rule incidents first. Phase 3 will enrich
them asynchronously; failed enrichment must retain the original rule incident.
This supersedes the failure behavior described in ADR 0002 and older docs.
