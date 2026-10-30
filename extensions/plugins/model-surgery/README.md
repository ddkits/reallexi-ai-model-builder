# Model Surgery community extension

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Apache-2.0. Core backlink: https://llm.reallexi.io

Open **Extensions → Model Surgery**. The guided page supports architecture
inspection, whole-layer expansion without a fixed size ceiling, raw-text
continual pre-training, held-out loss comparisons, prompt samples, cancellation,
and verified checkpoint history. Supported recipes are standard unquantized
Llama and Qwen2 causal text models in SafeTensors format.

See the [complete guide](../../../docs/MODEL_SURGERY.md) and
[wiki](../../../docs/wiki/Model-Surgery.md).

All runtime routes, pages, and code modules are declared in `plugin.json`.
No paid entitlement is required. The extension uses the existing local Admin
boundary and sandbox bridge, separate worker processes, and new output folders.
The core's existing Python dependencies supply Torch and Transformers.
