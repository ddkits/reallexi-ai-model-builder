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
2. **Heal:** train inserted layers or all parameters on raw text, with separate
   held-out evaluation and a fresh RAM/device/disk preflight.
3. **Review & use:** compare loss and prompt samples, then use the verified
   output folder with Transformers. Check representative external benchmarks
   before deployment.
4. **Run history:** inspect progress, cancellation, parentage, exact model size,
   output location, and saved evidence.

There is no fixed upper model size. Reachable sizes grow in complete layers;
architecture compatibility and available resources determine feasibility.
Expansion always creates a separate checkpoint. Healing creates another one.
Larger size alone is not a quality result, and there is no universal healing
token budget. Frozen original weights can still produce changed outputs when
new layers are trained.

The versioned [complete guide](https://github.com/ddkits/reallexi-ai-model-builder/blob/main/docs/MODEL_SURGERY.md)
covers source preparation, large local corpora, exact resource behavior,
initialization, held-out evaluation, recovery, and supported architectures.

The extension source and these wiki pages ship in the public package. Private
studios and commercial dependencies retain their separate release assignments.
