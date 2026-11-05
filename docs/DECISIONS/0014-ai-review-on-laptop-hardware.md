# AI review on the demo laptop

Date: 2026-11-06

## Measurements on the target laptop (i7-12700H, 15.7 GB RAM, RTX 3050 Ti 4 GB)

- `qwen2.5vl:3b` in native Windows Ollama 0.20.3 **cannot use the GPU**.
  With a 2048 context, one parallel slot, flash attention and a q8_0 KV
  cache, Ollama tries 7, 6, … 1 offloaded layers and settles on 0/37. The
  loaded footprint is reported as 10.7 GB (13.5 GB committed, about 3.5 GB
  resident), driven by the vision encoder's compute buffers, not the 3.2 GB
  of weights.
- On CPU it is fast once loaded: 5/5 and 6/6 warm runs returned validated
  JSON at a 1.9–2.1 s median for a 35-token answer
  (`docs/verification/native-ollama-gpu-qwen2.5vl-3b.json`). A full incident
  review (scene, verdict, observations, checks, limits) took 26–30 s,
  because generation runs at about 20 tokens/s.
- Loading is fragile with the Docker stack and a browser open: one attempt
  was refused ("requires more system memory (9.0 GiB) than is available");
  a retry loaded in about 2 minutes. Commit charge reached 53 of 57 GB.
- The OpenRouter free tier allows **50 requests per day**. It was exhausted
  during development, and every review then failed. Until this change, the
  failure was shown only as "HTTPStatusError".

## Decision

1. Rules decide; AI only reviews (ADR 0004, 0007). An incident is final
   without a review, so a slow or missing model never delays an alert.
2. Providers stay a `.env` switch: `ollama` (default), `openrouter`,
   `openai-compatible`. `SMARTOPS_MODEL_FALLBACK=ollama` lets a hosted
   primary fall back to native Ollama on rate limits, provider 5xx and
   timeouts. Only a local fallback is allowed, so evidence never reaches a
   second external service.
3. The model reviews the **clean** frame. The snapshot with burned-in boxes
   and scores led the model to describe "percentages indicating proximity".
4. The review asks for less output (at most 3 observations, 3 checks and 2
   limits, each under 160 characters) to bring CPU reviews under 30 s.
5. Every failure names its cause: daily limit, rate limit, rejected key,
   timeout, unreachable, invalid output.
6. `demo.ps1 up` warms the local model and keeps it loaded for 60 minutes,
   so the first live incident isn't the one that pays the two-minute load.

## Options that need the owner

- Pull a smaller vision model (for example a 1–2B model) and benchmark it
  for validated output. This is a download, so it needs approval.
- Buy $10 of OpenRouter credit, which raises the free-model limit to 1,000
  requests a day, or point `openai-compatible` at a paid endpoint.
- Raising WSL memory doesn't help: Ollama runs natively on Windows, outside
  the Docker VM.
