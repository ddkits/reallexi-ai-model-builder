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
3. Use **Prompt Test** to test the trained artifact. When exports are ready,
   compare the original runtime with regular standalone and custom final models.
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

For the adapter created by a completed training job, use **Trained Models →
Artifacts → Merge Trained Adapter + Base Model**. Enter a new merged model
name, build, then download the verified `<name>-safetensors.zip`. The name is
stored inside `reallexi-model.json` and displayed in the generated model card.
The separate **Custom Adapter Merge** area is for an adapter supplied outside
that training job.

## Edit Without Overwriting History

**Continue Phase** preserves an interrupted phase's checkpoint recipe and
reuses that phase's sample window. Successful phased runs load the completed
adapter or full model and advance automatically; intermediate phases do not
require a manual Continue action. **Edit & Retrain**, **Edit & Retry**, and
**Clone & Edit** load submitted settings into the full form so
model, data sources, numeric values, adapters, limits, checkpoint intervals,
and requested formats can be reviewed before a new child job starts. Runtime
checkpoint paths and prepared-cache internals stay with the source job. The
source job, proof, metrics, and artifact remain unchanged.
Edited names advance through clean `v2`, `v3`, and later versions.

## Custom Adapter Final Model

The Artifacts workspace can configure a PEFT adapter from an uploaded ZIP, a
local folder in the host-mounted data directory, or a Hugging Face adapter
repository. The adapter must contain `adapter_config.json` and adapter model
weights. Its recorded base model is auto-detected; an explicit mismatch blocks
the merge. Hugging Face validation also checks repository access and root
adapter weights before accepting the configuration. An inaccessible base is
reported with its direct model page before an export worker is started.

**Custom Adapter Final Model** safely merges the adapter into complete base
weights, saves verified sharded SafeTensors plus tokenizer/config and ownership
metadata, and packages a separate download that no longer requires PEFT. The
source adapter, trained artifact, and regular standalone export are preserved.
Local paths, uploaded ZIP members, and symbolic links are constrained before
extraction or loading. A ready final model can also be selected in the Publish
workspace for Hugging Face, GitHub Release, or an allowed local destination.

Hugging Face publication uses a verified container-local snapshot so large
weights stay stable when project data is mounted from Windows. Standard
HTTP/LFS transport avoids Docker/Xet missing-file failures. Successful publish
proof records the file count and bytes; failures remain in the training log and
job metrics so the same verified export can be retried without rebuilding it.

Core guidelines: https://llm.reallexi.io
