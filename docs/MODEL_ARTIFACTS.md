# Public Model Artifacts And Downloads Guide

Copyright (c) 2026 Reallexi LLC. All rights reserved.

This public-safe guide explains the artifact identities visible in AI Model
Builder without exposing application source or private operating procedures.

## Know What Was Trained

| Artifact | Meaning | Runtime dependency |
| --- | --- | --- |
| LoRA adapter | Small trained weight deltas plus adapter configuration | Recorded base model and an adapter-capable runtime |
| Native full model | Complete weights produced directly by the training strategy | Compatible model runtime |
| Standalone SafeTensors | Complete base weights with adapter deltas merged | Compatible Transformers runtime |
| GGUF Q8_0 | Complete quantized model for practical local serving | llama.cpp-compatible runtime |
| GGUF F16 | Complete higher-fidelity GGUF with larger storage needs | llama.cpp-compatible runtime |

A model-sized adapter can be tens of megabytes while its standalone model is
multiple gigabytes. That size difference is expected. The application keeps
the adapter download and standalone downloads separate and identifies the base
model required by an adapter.

SLM/LLM jobs default to LoRA for resource safety. Turning the LoRA Adapter
control off requests full-model fine-tuning and needs substantially more RAM or
VRAM; runtime preflight can reject an unsafe configuration.

## Use The Trained Model Workspace

1. Open a completed run under **Trained Models**.
2. Review **Training Proof** and **Metrics** before judging quality.
3. Use **Prompt Test** to test the trained artifact. When a standalone export
   is ready, compare it with the original adapter-plus-base runtime.
4. Open **Artifacts** to review parameter count, expected size, saved size,
   build status, and format-specific download.
5. Use **Inspect Files** to open the dedicated file page. Text, JSON, model
   cards, manifests, and ownership notices can be previewed without forcing a
   download; binary weights remain download-only.
6. Review every upstream model, tokenizer, adapter, and dataset license before
   publishing merged or quantized weights.

## Build And Validation States

Standalone formats can take time because complete base weights must be loaded,
merged, saved, converted, and checked. The UI reports queued, building, ready,
or failed, with current phase and progress. A download appears only after the
output passes format and plausible-size checks.

## Edit Without Overwriting History

**Continue** preserves the checkpoint recipe. **Edit & Retrain**, **Edit &
Retry**, and **Clone & Edit** load submitted settings into the full form so
model, data sources, numeric values, adapters, limits, checkpoint intervals,
and requested formats can be reviewed before a new child job starts. Runtime
checkpoint paths and prepared-cache internals stay with the source job. The
source job, proof, metrics, and artifact remain unchanged.
Edited names advance through clean `v2`, `v3`, and later versions.

Core guidelines: https://llm.reallexi.io
