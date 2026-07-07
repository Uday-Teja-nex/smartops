# ADR 0005: S3-compatible evidence storage

**Status**: accepted

## Context
Evidence artifacts (snapshots, thumbnails, clips) are binary, grow without
bound, and need access control plus future retention policies. Storing them
in Postgres or app containers violates durability and scaling rules.

## Decision
MinIO locally, any S3-compatible store in production. The worker uploads
under `{sourceId}/{candidateId}/…`; `evidence_items` rows are the catalog;
clients only ever receive short-TTL presigned URLs from
`GET /v1/evidence/{id}/url`. Presigning uses a browser-reachable public
endpoint configured separately from the internal service endpoint.

## Consequences
- Evidence survives container restarts and scales independently.
- One choke point for future role-based evidence restrictions and access
  auditing.
- Cost: two-endpoint configuration (internal vs public) that deployments
  must set correctly; URLs expire and must be re-requested.
