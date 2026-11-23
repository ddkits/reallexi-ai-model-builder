# Models and storage

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core backlink https://llm.reallexi.io

Open **Trained Models** to browse training jobs and runs from Model Surgery, Lexi Model
Pack, Image & LoRA, Audio & Voice, Video, and 3D Asset Studio. Search by name
or session ID, filter by source, and sort by name or modification date. The
runtime column identifies the local installation that owns each run. Frontends
connected to the same runtime show the same inventory.

1. Open **Details** beside a run to review its local files and dataset sources.
   Check several finished runs and choose **Check storage** for a combined
   preview. The total counts removable file bytes recursively and counts each
   selected session once.
2. Review the files, related datasets, and any blockers. A run can include
   checkpoints, exports, download archives, prepared data, logs, and history.
   Entire training phase chains and their automatic recovery attempts are
   reviewed together. Expanded and healed checkpoints from the same Model
   Surgery run share one selection.
3. Choose **Purge selected** to permanently remove the reviewed files and run
   records. If files change, run the storage check again. Running jobs and
   dependent runs can block deletion. Shared uploads, independently managed
   datasets, original files outside managed storage, caches, and repositories
   published to external services stay available.

The Models tab lists additional runtimes when the local operator connects
them. Each runtime reviews and applies its own purge. Check the result for
each runtime if a connection drops during a multi-runtime purge.
