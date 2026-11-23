# Models and storage

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core backlink https://llm.reallexi.io

Open the separate **Models** tab to browse training jobs and runs from Model Surgery, Lexi Model
Pack, Image & LoRA, Audio & Voice, Video, and 3D Asset Studio. Search by name
or session ID, filter by source, and sort by name or modification date. The
runtime column identifies the local installation that owns each run. Frontends
connected to the same runtime show the same inventory.

On Windows PCs running both the Docker CUDA and WSL ROCm stacks, the local
dashboards also combine their jobs in **Queue**, **Training**, and
**Trained Models**. Use the same job controls from either dashboard. Each
operation reaches the runtime that owns the job. Model files and datasets
stay in that runtime's storage. The native Linux ROCm Compose profile
requires Linux GPU device access. The Windows AMD launcher uses WSL ROCm.

1. Open **Details** beside a run to review its local files and dataset sources.
   Check individual runs or choose **Select all finished**. Then choose
   **Delete selected** to open the combined review. The total counts removable
   file bytes recursively and counts each selected session once.
   Selection skips active and paused runs, the models or checkpoints they
   need, and runs that depend on their outputs. Protected rows remain
   available for storage inspection.
   Check **Keep for later** on a run you plan to reuse. That run and the saved
   model, checkpoint, and prepared data inputs it relies on are protected
   until you clear the checkbox.
2. Review the files, related datasets, and any blockers. A run can include
   checkpoints, exports, download archives, prepared data, logs, and history.
   Entire training phase chains and their automatic recovery attempts are
   reviewed together. Expanded and healed checkpoints from the same Model
   Surgery run share one selection.
3. Choose **Delete permanently** to remove the reviewed files and run
   records. If files change, review the selection again. Running jobs and
   dependent runs can block deletion. Shared uploads, independently managed
   datasets, original files outside managed storage, caches, and repositories
   published to external services stay available.

The Models tab lists additional runtimes when the local operator connects
them. Each runtime reviews and applies its own purge. Check the result for
each runtime if a connection drops during a multi-runtime purge.
