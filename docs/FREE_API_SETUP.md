# Hosted model setup

Local YOLO remains the default continuous detector. Free API quotas are suitable
for experiments and sparse reviews, not three cameras at three frames per second
(777,600 frames per day). These adapters have mocked contract tests; no live
account, latency, accuracy, or quota acceptance has been established.

## OpenRouter

1. Sign in at https://openrouter.ai/workspaces/default/keys and create a key named
   `SmartOps`. Do not paste the key in chat or commit it.
2. Save the key in the ignored root `.env` as `SMARTOPS_MODEL_API_KEY=...`.
3. To opt into remote reviews, replace the following entries in `.env`:

```dotenv
SMARTOPS_MODEL_PROVIDER=openrouter
SMARTOPS_MODEL_BASE_URL=https://openrouter.ai/api/v1
SMARTOPS_TEXT_MODEL=nvidia/nemotron-3.5-super-vl:free
SMARTOPS_VISION_MODEL=nvidia/nemotron-3.5-super-vl:free
SMARTOPS_OPENROUTER_FREE_ONLY=true
SMARTOPS_OPENROUTER_DATA_COLLECTION=deny
SMARTOPS_MODEL_TIMEOUT_SECONDS=30
```

The named model was present in the public catalog when researched on October 27,
2026. Recheck https://openrouter.ai/api/v1/models before activation: free models
and supported parameters can change. The adapter requires an explicit `:free`
model, requests structured output, and does not fall back to paid models or retry
quota failures. A free suffix is not a local daily request budget.

Data collection defaults to `deny`. If no eligible provider supports that policy,
the request fails. Only choose `allow` deliberately for footage you are allowed
to share under the provider's terms. The application never relaxes it automatically.

Recreate the orchestrator after editing configuration:
`docker compose up -d --build --no-deps orchestrator`.
This configures review endpoints. Set `SMARTOPS_STREAM_ENRICHMENT=true` and
rebuild/recreate `stream-processor` to enable asynchronous reviews of new rule
incidents. The worker persists the rule incident first, waits for evidence
delivery, then requests one image review. It adds narrative/actions and
limitations without changing the measured event, severity, confidence, or
operator lifecycle state. Review failures remain explicit in review notes.

Automatic reviews have a shared durable cap of 40 requests per UTC day in
`/data/review-budget.db`; failed attempts count too. Manual probes and calls to
other review endpoints are outside that cap. Do not delete the budget database
to work around provider limits. Each source retains at most 20 pending images.
The orchestrator host port is loopback-only. Multi-host authentication and
production quota management remain outstanding.

## Optional Hugging Face CV experiments

Create a fine-grained token at https://huggingface.co/settings/tokens with
Inference Providers permission. Save `SMARTOPS_HF_TOKEN` in `.env`. Set
`SMARTOPS_DETECTOR_BACKEND=huggingface` and optionally
`SMARTOPS_HF_MODEL=facebook/detr-resnet-50`, then rebuild/recreate only the detector.
This uploads JPEG frames to Hugging Face. Do not enable it for unattended streams:
there is no local spend cap, and available credits/provider limits apply.
Restore `ultralytics-cpu` to return to local detection.

The adapter uses HF Inference, validates normalized boxes and scores, and raises
on unavailable models, malformed results, and rate limits. It does not turn failed
inference into a claim that a scene is empty. This is object detection, not a
validated replacement for tracking, event rules, or segmentation.

## Pricing and policy references

- [OpenRouter pricing](https://openrouter.ai/pricing/): free tier advertised at
  50 requests/day when researched; no service-level guarantee.
- [OpenRouter data collection](https://openrouter.ai/docs/guides/privacy/data-collection).
- [Hugging Face credits](https://huggingface.co/docs/inference-providers/pricing):
  free accounts receive a small monthly credit, not unlimited free CV.
- [HF object detection](https://huggingface.co/docs/inference-providers/tasks/object-detection)
  and [HF Inference endpoint](https://huggingface.co/docs/inference-providers/providers/hf-inference).
- [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits): Contributor data
  sharing pricing and SAM inference are paid. Do not assume data sharing grants
  a generally free Meta API. The optional `meta` compatible adapter is not a free preset.

Never print resolved Docker Compose configuration when keys are present; it
contains interpolated secrets. Do not commit `.env` or include keys in diagnostics.
