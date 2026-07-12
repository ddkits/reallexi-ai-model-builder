<!-- SPDX-FileCopyrightText: 2026 Reallexi LLC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GPU acceleration and device selection

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core project: https://llm.reallexi.io

AI Model Builder separates **GPUs detected by the host OS** from GPUs that are
**usable by the backend runtime**. A display adapter appearing in Windows Device
Manager does not mean a Linux Docker container or its installed PyTorch wheel can
use that adapter.

## Automatic launcher behavior

`npm run project` inventories graphics devices and chooses a compatible Compose
override:

| Host/runtime | Selection | PyTorch device |
| --- | --- | --- |
| Windows or Linux with NVIDIA Container Toolkit | NVIDIA CUDA image | `cuda:N` |
| Native Linux with `/dev/kfd`, `/dev/dri`, and ROCm | AMD ROCm image | `cuda:N` |
| Native macOS Python process with MPS (outside Docker) | Apple Metal | `mps` |
| No usable accelerator | CPU image | `cpu` |

PyTorch deliberately uses the `torch.cuda` API and `cuda:N` device spelling for
both NVIDIA CUDA and AMD ROCm. The backend uses `torch.version.hip` to label ROCm
correctly instead of assuming every `cuda:N` device is NVIDIA.

When both AMD and NVIDIA adapters exist on Windows, the Docker launcher selects
NVIDIA if the NVIDIA container runtime works. Windows AMD adapters remain visible
in diagnostics as `Host only`: Docker Desktop's Linux CUDA container cannot use
them. An RX 7900 XT can use the ROCm profile on a supported native Linux host,
but it cannot share one PyTorch process with the CUDA wheel.

## Choosing a GPU

The training form lists each runtime device separately. `Auto` selects the usable
accelerator with the most visible VRAM. Selecting a device stores its stable
runtime id, such as `cuda:0` or `rocm:0`, in the recipe. `CPU Only` is always an
explicit option. A requested device that is unavailable is recorded in the job
log and safely falls back to CPU; it is never reported as active GPU training.

Every job persists:

* requested device id;
* resolved PyTorch device and index;
* accelerator vendor, name, backend, and visible VRAM;
* effective RAM/VRAM limits and any fallback warning.

This evidence is available in the job's `runtimeResourcePlan` and preserved logs.

## Overrides and troubleshooting

Set `REALLEXI_ACCELERATOR_BACKEND` to `auto` (default), `nvidia`, `amd`, or `cpu`
before `npm run project`. An unavailable forced backend safely resolves to CPU.

For NVIDIA, verify `nvidia-smi` works on the host and inside a test container.
For AMD ROCm, use native Linux with a supported amdgpu driver and verify
`/dev/kfd` and `/dev/dri` exist. Do not install a CUDA and ROCm PyTorch wheel into
the same backend image. In Windows Task Manager, inspect the CUDA/Compute engine;
the default 3D graph can stay low during active CUDA training.

The `/system/resources` endpoint returns `host_os`, `runtime_os`, `accelerators`,
`selected_accelerator`, and backward-compatible CUDA summary fields for clients.
