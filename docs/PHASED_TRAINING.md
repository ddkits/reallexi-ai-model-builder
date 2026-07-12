# Phased And Incremental Training

Copyright (c) 2026 Reallexi LLC. All rights reserved.

AI Model Builder divides one large sample target into bounded, non-overlapping
training windows. Every successful phase saves a usable LoRA adapter or full
model, checkpoint, metrics, provenance, and lineage before the next configured
window starts automatically.

The internal phase records stay separate for recovery and auditability. The UI
groups those records as one logical model-training chain so contributors and
builders see truthful overall progress instead of a stack of unrelated jobs.

## Lifecycle At A Glance

1. Plan one total sample target.
2. Resolve a RAM-aware or fixed phase window.
3. Prepare and train only that non-overlapping window.
4. Save checkpoint, proof, metrics, and a usable model artifact.
5. Queue the next configured window automatically.
6. Repeat until the original target is reached.

If a phase is interrupted, **Continue Phase** returns to the same window. It
does not skip forward, repeat a completed phase as a new model, or extend the
configured target.

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
5. Successful intermediate phases load their completed adapter or full model
   and advance to the next non-overlapping window automatically.
6. **Continue Phase** on a failed or cancelled phase resumes that same phase and
   can reuse its checkpoint and prepared rows.
7. Automatic training stops at the configured target. Use an intentional
   clone, edit, or retrain workflow to create a different target or lineage.
8. A zero checkpoint interval disables periodic saves; the required phase-end
   checkpoint is still written.

## Progress Is Chain Progress

The phase worker can finish 100% of its local window while the full model chain
is only partially complete. The overall progress bar sums actual
`trained_samples` from one canonical successful job per phase, excludes
recovery duplicates, and adds only the prepared-row estimate for an active
phase. It never awards progress for rows a source did not return.

For example:

| Value | Samples |
| --- | ---: |
| Configured target | 20,000 |
| Actual rows learned after phase 5 | 1,250 |
| Local phase completion | 100% |
| Logical chain completion | 6.25% |

The UI uses **Advancing** between a successful intermediate phase and its next
queued child. **Completed** is reserved for the final configured target.

If an earlier phase has a real shortfall, the chain keeps the same 20,000-row
target and continues until cumulative learned rows reach it. Additional phase
numbers complete the original target; they do not increase it.

## Five-Phase Example

For a 5,000-sample target and 1,000 samples per phase:

| Phase | Sample range | Overall result |
| --- | --- | ---: |
| 1 / 5 | 0-1,000 | 20%; phase 2 starts automatically |
| 2 / 5 | 1,000-2,000 | 40%; phase 3 starts automatically |
| 3 / 5 | 2,000-3,000 | 60%; phase 4 starts automatically |
| 4 / 5 | 3,000-4,000 | 80%; phase 5 starts automatically |
| 5 / 5 | 4,000-5,000 | 100%; configured target complete |

Later phases consume the previous phase artifact internally. The grouped UI
still displays the original selected model as the logical chain's model.

## Recovery Flow

**Continue Phase** is shown only when the current logical phase is failed or
cancelled:

1. Review the latest phase logs and resource notes.
2. Choose **Continue Phase** once.
3. Resume the newest valid model checkpoint when available.
4. Reuse prepared rows only when their recipe and exact phase-window
   fingerprint match.
5. Otherwise prepare the same deterministic source window again.
6. Resume automatic phase advancement after the recovery succeeds.

Repeated clicks while a recovery is already queued or active reuse one
canonical attempt. If recovery is interrupted again, the next Continue Phase
follows the newest failed attempt and its most recent safe state.

A prepared file from a parent or previous phase is rejected even when it is in
the same lineage. The mismatch stays in the job's warning log, and recovery
prepares fresh rows for the interrupted phase instead of duplicating an older
window.

| Situation | Public state | Next action |
| --- | --- | --- |
| User pause | Paused | Resume the same worker |
| User stop | Cancelled | Continue Phase |
| Worker or memory failure | Failed | Review resources, then Continue Phase |
| Restart during work | Failed/recoverable | Continue Phase |
| Restart between artifact save and next queue | Advancing | No action; automatic reconciliation resumes |
| Artifact cannot be saved | Failed | Resolve storage/access, then Continue Phase |

A Stop request prevents automatic advancement even if it arrives near the end
of evaluation or artifact saving.

CUDA plans retain headroom for drivers, kernels, and allocator fragmentation.
Full-model preflight includes optimizer, gradient, and activation memory. After
a CUDA OOM, an SLM/LLM recovery can change full-model tuning to LoRA, reduce the
micro-batch, preserve effective batch through accumulation, and reuse the exact
prepared phase rows.

## Why Internal Records Still Exist

Each phase retains its own:

* bounded sample range and source allocation;
* prepared-data fingerprint;
* interval and phase-end checkpoints;
* metrics and resource plan;
* training proof and source provenance;
* LoRA adapter or full-model artifact; and
* parent, root, and stable phase-chain lineage.

The grouped Logs tab reads the linked internal jobs chronologically, labels
each entry with its job number, and exposes preparation, source-budget,
checkpoint, training, evaluation, artifact-save, transition, and failure
evidence. A successful phase writes an explicit evidence line with learned rows
for the job, cumulative learned rows versus target, and its source budget.

These records make recovery and audit possible. Grouping changes presentation,
not history: a user sees one model chain while maintainers can still trace every
successful or interrupted phase.

With multiple selected sources, each available source receives a deterministic
fair share of every phase. Missing, gated, incompatible, or exhausted sources
are recorded for review. Their unused allocation is reassigned to sources that
still have usable rows, up to the recipe's per-source limits.

For a 1,000-sample phase and four sources, the nominal allocation is 250 rows
per source. If one source is unavailable, its 250 rows are redistributed among
the healthy sources. The proof stores every source's exact `sample_start` and
`sample_end`; those end cursors become the next phase's starts so redistributed
rows cannot be learned twice. Prepared-dataset metadata preserves this budget
evidence during interruption recovery.

Phasing limits dataset preparation and run duration. It does not make an
oversized base model fit into RAM or VRAM; model resource preflight still
applies. LoRA adapters are the faster low-memory choice. Full-model training
updates and saves all weights and requires substantially more resources.

## Contribution Opportunities

Public contributors can improve phased training without exposing private
application source by proposing:

* clearer lifecycle and recovery documentation;
* accessibility and mobile presentation improvements;
* synthetic phase-progress examples;
* dataset metadata and provenance reviews;
* reproducible failure reports with secrets and customer material removed;
* test scenarios for source exhaustion, interruption, and artifact identity;
* plugin or theme proposals through documented manifests; and
* translations of public-safe concepts and terminology.

See [CONTRIBUTING.md](../CONTRIBUTING.md) and
[PLUGIN_HOOKS.md](PLUGIN_HOOKS.md) before submitting a change.

Core guidelines: https://llm.reallexi.io
