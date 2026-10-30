# Model Surgery: expand, heal, and evaluate

Copyright (c) 2026 Reallexi LLC. All rights reserved.

Core backlink: https://llm.reallexi.io

Model Surgery is an Apache-2.0 community extension. Its source is shipped in
`extensions/plugins/model-surgery/` in the public distribution. It has no paid
capability dependency. Private studios, commercial code, credentials, and local
model/data files are not included with it.

## Open the workspace

Start AI Model Builder using its normal launcher. Open **Extensions**, select
**Model Surgery**, unlock the page using the existing local Admin access flow,
then select **Connect workspace**. The shell keeps the credential; the sandboxed
page only requests manifest-declared operations.

The public launcher mounts this extension into its runtime image. Existing
installations need the updated generated public package and a runtime that
supports reviewed extensions and the Admin bridge. The extension uses the
runtime's existing Torch, Transformers, SafeTensors, and Hub dependencies.

## 1. Plan and expand

The **Your models** picker loads automatically when you connect. It groups
completed training jobs, existing merged SafeTensors exports, local model
folders, downloaded Hugging Face checkpoints, and previous surgery outputs.
Search by model name, job number, architecture, or folder. Selecting a model
fills the source path for you.

Adapter-only, unsupported, incomplete, missing, and numerically rejected models
remain listed. Select one to see its preparation message. For a trained LoRA
adapter, build a merged full SafeTensors export in **Trained Models**, then use
**Refresh models** and choose that merged export. GGUF and media pipeline outputs
are visible for context but are not full text checkpoints for this recipe.

Discovery reads metadata only; it never loads or downloads model weights.
Default locations include the application's artifact and export stores,
extension-owned artifact folders, mounted `local-inputs/`, local `models/`, and
the backend's Hugging Face cache. **Folders checked & discovery notes** shows
what this runtime can see. To find another location, mount it into the backend
and use **Scan another folder**, or enter its exact model path directly.
Folder scans are bounded; choose a more specific parent if a large/deep folder
reports incomplete discovery. Administrators can configure additional defaults
with `REALLEXI_MODEL_SURGERY_MODEL_DIRS`, separated by the platform's path-list
separator. Nothing is scanned across the entire drive or home directory.

1. Select an existing model, or enter a Hugging Face ID or accessible local directory.
   For gated repositories, configure your account in the existing local Hub
   workspace. The planner resolves a Hub revision to a commit.
2. Use a full, unquantized **Llama or Qwen2 text causal LM** checkpoint with
   SafeTensors weights and its tokenizer. Adapter-only, GGUF, sliding-window,
   multimodal, mixture-of-experts, and custom-code architectures are not recipes
   supported by this version. Merge adapters before surgery.
3. Select **Inspect model & preview growth** to count parameters without
   allocating weights. Then choose a 25%/50% layer-growth preset or enter a
   target size in billions and select **Calculate layer plan**. The helper
   chooses a middle layer and calculates the extra copies. Advanced layer
   choices are available under **Advanced: choose the layers yourself**.
   The preview shows source layers + block length × extra copies = new depth.
   **Use the middle third** offers a convenient
   starting block. It is a helper, not a proven optimal layer selection.
4. Optionally enter a target size in billions. The helper chooses the nearest
   reachable larger size using copies of a single middle layer. The exact
   parameter count is shown before starting.
5. Choose **Identity residuals** or **Copy existing weights**. Identity
   copies the selected layers, then zeros each new attention output and MLP
   output projection. The worker compares source/expanded probe logits before
   saving. Copy mode preserves the copied weights but can disrupt behavior.
6. Create the expanded checkpoint. The worker saves it separately, reloads it,
   checks the layer count, parameter count, weights, and finite output, then
   publishes it in history with **needs healing** status.

### What should I pick?

Use **Identity residuals** as the starting initialization and use the size
helper for your model's actual structure. For **Qwen2.5-1.5B**, whose source
configuration has 28 layers and 1,543,714,304 parameters, a target of 2B is
reachable with first layer 14, a block length of 1, and 10 additional copies.
That gives 38 layers and 2,011,692,544 parameters. Other models need their own
calculated plan.

| Option | Meaning and starting choice |
| --- | --- |
| Model source | Select from Your models; its actual backend path fills automatically. Enter a Hub ID only for an online model not already listed. |
| Hub revision | For online Hub sources, leave `main` unless you need a particular tag/commit. Inspection pins it. Local selections do not use this field. |
| First layer | Copy position, starting at 0. It chooses where to copy from, not how much bigger the model becomes. The helper chooses a middle layer. |
| Layers in the block | Number of consecutive source layers copied together. Start with 1 when using the target-size helper. |
| Additional block copies | Extra repeats of that block. A block of 4 copied 2 additional times adds 8 layers. |
| Identity residuals | Recommended initial behavior-preservation mode; the worker checks source probe output before saving. Training and evaluation are still needed. |
| Copy existing weights | Reapply the original copied weights at their new positions. Outputs can change immediately; use for depth-stacking experiments followed by healing. |

There is **no fixed model-size ceiling** or one-time expansion limit. Complete
layers determine reachable sizes; embeddings and the output head do not grow.
The same ratio of layer counts and total parameters therefore generally differs.
Expand a completed checkpoint again when desired. Each growth operation records
its own source and newest inserted layer positions.

Resource estimates and current RAM/disk availability determine whether a run can
start. Expansion uses CPU float32 weights for predictable serialization. A Hub
download also consumes cache space. Estimates cannot guarantee that an operating
system or competing workload will leave enough resources throughout the run.

## 2. Heal with continual pre-training

Select **Heal this checkpoint** in history. Provide UTF-8 `.txt` or `.md` files
for training and separate held-out evaluation. Small files up to 16 MiB each can
be uploaded from the page. Larger corpora use mounted backend-accessible paths.
The source checkout mounts `local-inputs/` read-only at `/app/local-inputs/`.
The public package provides the same mount. Paths inside a container refer to
that container, not to an arbitrary host directory.

Choose **Inserted layers only** to freeze the original parameters, or **All
model parameters** for full continual pre-training. The selected weights are
trained directly with AdamW; this workflow does not substitute LoRA. CPU and
runtime-visible CUDA/ROCm accelerators are available. Gradient checkpointing,
microbatch size one, and configurable accumulation reduce activation memory.
Float32 weights, gradients, and optimizer state still require substantial
memory. Distributed DeepSpeed, GaLore, quantized training, and optimizer-state
resumption are not implemented by this extension.

Set sequence length within the model's context window, learning rate, optimizer
steps, accumulation, and evaluation blocks. Check resources and start a small
pilot. The worker streams bounded text blocks, trains next-token prediction,
and cycles through the training file if the configured steps require it.
History records token exposures and repeated passes; rereading a corpus does
not create additional unique data. Input files should stay unchanged during
the run. Their hashes are retained in provenance.

General-purpose goals need broad, clean, appropriately licensed text, including
representative general-language evaluation. Domain goals need representative
domain text plus a retention strategy and general evaluation. Choose mixtures
and token budgets from experiments. There is no universal minimum of 1, 5, 10,
or 50 billion tokens that guarantees healing, and a particular replay percentage
does not guarantee protection from forgetting.

Evaluation measures token-weighted loss on a fixed number of blocks from the
start of your held-out file before and after training. Keep that file out of
training; matching file paths and identical contents are rejected. The tool
cannot detect every semantic overlap. Shuffle or curate representative held-out
text beforehand. The resulting model is saved into a new folder and reloaded
before completion. A lower loss on this sample does not certify broad quality.

## 3. Review and use

Run the same prompt samples and external task benchmarks against the original,
expanded, and healed models. The page can run deterministic CPU prompt tests on
any verified expansion/healing checkpoint. It does not certify the checkpoint
for deployment or automatically publish it.

History shows the backend model directory. Each verified output contains a
standard Transformers configuration, SafeTensors weights, tokenizer, and
`model_surgery.json` report. Load the folder with Transformers or use it as a
parent in this workspace. Healing from a previous healed checkpoint starts a
fresh optimizer. Ordinary training history and export workflows are separate.

## Recovery and troubleshooting

- **Insufficient memory or disk:** reduce added layers, sequence length, or the
  trainable scope; free resources or move to stronger hardware. There is no
  automatic smaller-model or LoRA fallback.
- **Unsupported architecture:** use one of the stated recipes. A new model
  family needs explicit configuration, cache, layer-layout, and reload tests.
- **Non-finite loss/weights:** the run fails without publishing its partial
  checkpoint. Review the corpus, source checkpoint, and learning rate, then
  create another run from the preserved parent.
- **Cancellation:** requested cancellation is checked between loading/saving
  stages and training microsteps. A large download or save must return before
  cancellation takes effect. Partial output remains in that run's folder and
  is never listed as a verified checkpoint.
- **Interrupted worker:** history marks it failed. Parent models remain
  available. Start a new run; interrupted optimizer state is not resumable.
- **Other training active:** finish or pause core training before starting a
  surgery worker. This extension runs one surgery/healing/prompt worker at a time.

## Background

[SOLAR](https://arxiv.org/abs/2312.15166) studies depth up-scaling followed by
continued pre-training. This extension's contiguous-block recipe is not a
reproduction of the complete SOLAR training recipe. Function-preserving growth
is also explored in [Net2Net](https://arxiv.org/abs/1511.05641); the residual
initialization here is explicitly checked on a probe and is not a guarantee
that every later training step will preserve the base model's behavior.

See the [wiki guide](wiki/Model-Surgery.md), [extensions](EXTENSIONS.md), and
[phased training](PHASED_TRAINING.md) for related workflows.
