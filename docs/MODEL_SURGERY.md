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

1. Choose a Hugging Face model ID or a backend-accessible local model directory.
   For gated repositories, configure your account in the existing local Hub
   workspace. The planner resolves a Hub revision to a commit.
2. Use a full, unquantized **Llama or Qwen2 text causal LM** checkpoint with
   SafeTensors weights and its tokenizer. Adapter-only, GGUF, sliding-window,
   multimodal, mixture-of-experts, and custom-code architectures are not recipes
   supported by this version. Merge adapters before surgery.
3. Select the first layer (numbered from zero), block length, and additional
   block copies. **Check architecture & resources** counts parameters without
   allocating model weights. **Use the middle third** offers a convenient
   starting block. It is a helper, not a proven optimal layer selection.
4. Optionally enter a target size in billions. The helper chooses the nearest
   reachable larger size using copies of a single middle layer. The exact
   parameter count is shown before starting.
5. Choose **Identity residuals** or **Copy original layer weights**. Identity
   copies the selected layers, then zeros each new attention output and MLP
   output projection. The worker compares source/expanded probe logits before
   saving. Copy mode preserves the copied weights but can disrupt behavior.
6. Create the expanded checkpoint. The worker saves it separately, reloads it,
   checks the layer count, parameter count, weights, and finite output, then
   publishes it in history with **needs healing** status.

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
