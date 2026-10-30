# GPU acceleration

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core backlink: https://llm.reallexi.io

The launcher inventories host graphics devices and distinguishes host hardware
from accelerators actually available to the training runtime. A detected GPU
does not by itself establish that a container can use it.

NVIDIA training needs a compatible CUDA runtime and container device access.
AMD training needs a supported ROCm environment. Apple MPS depends on native
runtime support. CPU remains an available local option. Use the workspace's
resource report to check the selected device and available memory before a run.

Model Surgery performs expansion on CPU and checks RAM and disk first. Its
healing page lists CPU and runtime-visible CUDA/ROCm devices and estimates
float32 model, gradient, optimizer, and activation memory before training.
It has no fixed model-size ceiling; resource fit and the supported architecture
determine feasibility. See [Model Surgery](MODEL_SURGERY.md).

Keep application ports in the documented 54376–64322 range. Follow the public
launcher instructions for your release and the hardware vendor's official
compatibility guidance. Do not assume that inference memory equals training
memory, or that a host device report proves accelerator access inside Docker.
