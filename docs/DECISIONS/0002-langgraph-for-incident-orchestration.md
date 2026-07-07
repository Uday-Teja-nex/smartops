# ADR 0002: LangGraph for incident orchestration

**Status**: accepted

## Context
Turning detector candidates into incidents is a stateful, branching
workflow: gather evidence, decide whether to spend VLM time, classify,
summarize, apply policy, and route to operations or human review — with
honest fallbacks at every step.

## Decision
The orchestrator service owns a LangGraph `StateGraph`
(`ingest_candidate → gather_evidence → should_review ⇒ vlm/human/ignore →
llm_summary → apply_policy`). LangGraph handles decisions only; video
transport, frame decoding, and detection loops live in ingest/worker/
detector services.

## Consequences
- Routing policy is explicit, testable (FakeProvider unit tests), and
  inspectable (`GET /v1/graph`).
- Future flows (escalation chains, report generation, cross-feed
  correlation) extend the graph without touching transport code.
- Cost: one more framework dependency; kept isolated to the orchestrator.
