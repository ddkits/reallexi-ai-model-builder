# Model Surgery community extension

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Apache-2.0. Core backlink: https://llm.reallexi.io

Open **Extensions → Model Surgery**. The guided page supports architecture
planning with a searchable **Your models** picker for trained artifacts, merged
exports, local folders, cached Hub checkpoints, and earlier surgery outputs.
Ineligible formats remain visible with preparation steps. Discovery reads
metadata only and supports explicit mounted-folder scans. The page also supports
inspection, whole-layer expansion without a fixed size ceiling, raw-text
continual pre-training, held-out loss comparisons, prompt samples, cancellation,
and verified checkpoint history. Supported recipes are standard unquantized
Llama and Qwen2 causal text models in SafeTensors format.

See the [complete guide](../../../docs/MODEL_SURGERY.md) and
[wiki](../../../docs/wiki/Model-Surgery.md).

Prepare a healing recipe to run expansion and training together. The worker
reserves resources for both checkpoints, checks the source and candidate on the
same held-out text, and keeps the verified expansion available if healing stops.
Prompt tests use the saved chat template when present. Generated model cards
carry Reallexi LLC tool copyright and retain upstream license files.

All runtime routes, pages, and code modules are declared in `plugin.json`.
No paid entitlement is required. The extension uses the existing local Admin
boundary and sandbox bridge, separate worker processes, and new output folders.
The core's existing Python dependencies supply Torch and Transformers.

The Heal page can collect public Reallexi websites, linked subdomains, and direct
app-store listings into a reusable ZIP (`documents.jsonl`, `apps.json`,
`links.csv`, training/evaluation text, and coverage/terms). An opt-in pipeline
starts full-model healing only after fresh resource and active-job checks.
Outputs are named Lexi by measured size; loader identifiers and upstream
dependency/license metadata remain valid. The `ui:download` permission enables
ZIP downloads within this extension's sandbox.
