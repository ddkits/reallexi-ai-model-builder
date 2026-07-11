# Phased And Incremental Training

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder can divide a large sample target into bounded phases. Each
phase saves a usable local adapter or full-model artifact before the next phase
starts, which gives constrained systems a shorter path to a testable model.

## Public Behavior Contract

1. **Max Samples** is the total target; **Samples / Phase** is the bounded data
   window. A value of `0` selects RAM-aware automatic sizing.
2. Fixed phase sizes support `250` through `10,000` samples. Useful starting
   values are `500` for smoke tests, `1,000-2,500` for laptops, and `5,000`
   for larger systems.
3. **Select All Results** adds every source matching the active Source Finder
   filters so all available selected sources can share each phase.
4. Every completed phase records its sample range, source provenance, metrics,
   checkpoint, artifact type, parent job, and root lineage.
5. **Continue Training** loads the completed adapter or full model and advances
   to the next non-overlapping source window.
6. **Continue** on a failed or cancelled phase resumes that same phase and can
   reuse its prepared rows. It does not advance the source window.
7. Continuing after the configured target extends the target by one phase. The
   previous good artifact remains available if a later source is exhausted.
8. A zero checkpoint interval disables periodic saves; the required phase-end
   checkpoint is still written.

With multiple selected sources, each available source receives a deterministic
fair share of every phase. Missing, gated, incompatible, or exhausted sources
are recorded for review.

Phasing limits dataset preparation and run duration. It does not make an
oversized base model fit into RAM or VRAM; model resource preflight still
applies. LoRA adapters are the faster low-memory choice. Full-model training
updates and saves all weights and requires substantially more resources.

Core guidelines: https://llm.reallexi.io
