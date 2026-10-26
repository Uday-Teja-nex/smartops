# 0008 — Bound local model requests

Date: 2026-10-26

The original 480-second model timeout allows unusably late reviews. Default
requests now use a 30-second HTTP timeout, 2048 context tokens, a 32-token
prompt batch and at most 256 generated tokens. Invalid, nonfinite and
nonpositive timeout configuration fails startup instead of silently falling
back. Explicit deployments can override the timeout. Model residency is ten
minutes to reduce repeated loads; startup warmup still needs implementation.

The native Qwen 2.5 VL 3B probe completed once in 112.12 seconds, of which
92.67 seconds was loading. Ollama logs reported CPU weights and compute graph,
so this is not GPU acceptance. A later repeat probe timed out loading again.
These settings bound failure; they do not establish the Phase 3 latency,
accuracy or GPU requirements. HTTP timeout is per network operation, not a
whole enrichment workflow deadline; the asynchronous workflow must enforce
its own total deadline.

API behavior is grounded in Ollama's official
[structured output documentation](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx),
[runtime options](https://github.com/ollama/ollama/blob/main/api/types.go), and
[model residency documentation](https://github.com/ollama/ollama/blob/main/docs/faq.mdx).
