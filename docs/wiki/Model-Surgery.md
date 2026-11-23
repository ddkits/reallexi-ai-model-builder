# Model Surgery

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core backlink: https://llm.reallexi.io

Open **Extensions → Model Surgery** in the local workspace and connect using
the existing Plugin Admin Unlock. This free community extension offers:

1. **Plan & expand:** select a trained model, merged export, local folder,
   downloaded Hub checkpoint, or earlier surgery result from **Your models**.
   Search the list or scan a mounted folder. Models needing preparation remain
   visible with a reason. Choose a full SafeTensors Llama or Qwen2 text model,
   inspect it, and choose a growth preset or calculate a target size. The page
   explains each advanced option and recommends identity initialization.
   To train automatically, configure files, rights, and training options on
   **Heal**, then return to **Plan & expand**, enable automatic healing,
   inspect the plan, and select **Expand & train**. The worker verifies the
   new checkpoint before training. If healing stops, the expansion remains
   available in history. For a standalone expansion, select **Start expansion**
   and use **Continue to healing** when ready.
2. **Heal:** train inserted layers or all parameters on raw text, with separate
   held-out evaluation and a fresh RAM/device/disk preflight.
   **Build Reallexi dataset** collects public reallexi.io pages, linked
   subdomains, and direct app-store listings. Download its reusable ZIP with
   source JSONL, `apps.json`, link CSV, training/evaluation text, and coverage
   manifest. Enable optional automatic all-parameter training after selecting
   a parent/settings and confirming rights. Failed memory or active-job checks
   preserve the dataset and explain why training did not start.
   **Prepare full GPU training settings** selects full scope, a detected NVIDIA
   GPU, and Smart phases. The fresh preflight chooses the optimizer based on
   available memory and runtime support.
3. **Review & use:** compare held-out loss from the starting model, expanded
   checkpoint, and healed candidate in a combined run. Test representative
   chat prompts with the model's template or choose raw completion. Use the verified
   output folder with Transformers, or filter **Trained Models** to
   **Model Surgery**, select the checkpoint, and choose **Use for training**.
   Check representative external benchmarks before deployment.
4. **Run history:** inspect progress, cancellation, parentage, exact model size,
   output location, and saved evidence.

There is no fixed upper model size. Reachable sizes grow in complete layers;
architecture compatibility and available resources determine feasibility.
Expansion always creates a separate checkpoint. Healing creates another one.
Outputs display **Lexi {size}B** and new files save the measured model name.
The architecture identifiers and source dependencies needed for loading remain
valid; upstream attribution and license requirements remain attached.
Larger size alone is not a quality result, and there is no universal healing
token budget. Frozen original weights can still produce changed outputs when
new layers are trained.

The versioned [complete guide](https://github.com/ddkits/reallexi-ai-model-builder/blob/main/docs/MODEL_SURGERY.md)
covers source preparation, large local corpora, exact resource behavior,
initialization, held-out evaluation, recovery, and supported architectures.

The extension source and these wiki pages ship in the public package. Private
studios and commercial dependencies retain their separate release assignments.

Healing defaults to **Smart phases**. It retains the selected model and scope,
chooses a fitting optimizer, and can stream gradients and Adam state to disk
with bounded buffers or select CPU execution. All operations save bounded
checkpoint shards. Disk optimizer working state is not resumable. Resident
weights must still fit; dividing a corpus into chunks cannot remove that floor.
Readiness reports backend RAM and GPU VRAM separately. Docker/WSL may expose
only part of Windows' installed RAM. RAM estimates already include headroom.
