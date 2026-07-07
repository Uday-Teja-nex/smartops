# ADR 0003: Local open-source models first

**Status**: accepted

## Context
No inference budget during development; CCTV frames are privacy-sensitive;
the product must nevertheless be upgradeable to hosted models.

## Decision
Ollama is the default model runtime with small open models
(`qwen2.5vl:3b` vision, `llama3.2:3b` text). All model access goes through
the `ModelProvider` interface; provider choice is `SMARTOPS_MODEL_PROVIDER`
config. Structured outputs (JSON schema) + Pydantic validation are required
regardless of provider.

## Consequences
- Zero-cost, on-prem-friendly default; evidence never leaves the machine.
- Hosted APIs (e.g. Claude) become a provider class, not a rewrite.
- Cost: CPU inference is slow and memory-hungry; the confidence/fallback
  policy (human_review) absorbs model failures honestly rather than
  degrading correctness.
