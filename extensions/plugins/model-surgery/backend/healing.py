# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Bounded-memory raw-text continual pre-training for expanded checkpoints."""
from __future__ import annotations

import gc
import hashlib
import importlib
import math
from pathlib import Path

surgery = importlib.import_module("extensions.plugins.model-surgery.backend.surgery")


def options(request):
    result = {"steps": surgery.integer(request.get("steps", 100), "Optimizer steps"),
              "sequence_length": surgery.integer(request.get("sequence_length", 256), "Sequence length", 2),
              "accumulation": surgery.integer(request.get("accumulation", 1), "Gradient accumulation"),
              "eval_blocks": surgery.integer(request.get("eval_blocks", 8), "Evaluation blocks")}
    rate = float(request.get("learning_rate", 1e-5))
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Learning rate must be finite and positive.")
    result.update(learning_rate=rate, train_scope=str(request.get("train_scope") or "inserted"),
                  device=str(request.get("device") or "cpu"))
    if result["train_scope"] not in {"inserted", "full"}:
        raise ValueError("Train inserted layers or the full model.")
    device = result["device"]
    if device != "cpu" and not (device.startswith("cuda:") and device[5:].isdigit()):
        raise ValueError("Select CPU or a detected CUDA/ROCm device.")
    return result


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def preflight(request, output_root):
    import torch
    config, _ = surgery.configuration(request["source"])
    settings = options(request)
    if settings["sequence_length"] > config.max_position_embeddings:
        raise ValueError("Sequence length exceeds the model context window.")
    evidence = surgery.read_json(Path(request["source"]) / "model_surgery.json")
    train, evaluation = Path(request["train_file"]), Path(request["eval_file"])
    for path in (train, evaluation):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md"} or path.stat().st_size == 0:
            raise ValueError("Use nonempty UTF-8 .txt or .md files for training and held-out evaluation.")
    if train.resolve() == evaluation.resolve():
        raise ValueError("Use a separate held-out evaluation file.")
    if not request.get("data_rights_confirmed"):
        raise ValueError("Confirm that you have permission to train on the selected text.")
    total = evidence["expanded_parameters"]
    added = total - evidence["original_parameters"]
    trainable = added if settings["train_scope"] == "inserted" else total
    activation = config.num_hidden_layers * config.hidden_size * settings["sequence_length"] * 64 / surgery.GIB
    training_gb = (total * 4 + trainable * 12) / surgery.GIB + activation + 1
    capacity = surgery.resources(output_root)
    ram_gb = max(total * 4 / surgery.GIB * 1.6 + 1, training_gb if settings["device"] == "cpu" else 0)
    disk_gb = total * 4 / surgery.GIB * 1.1 + .1
    blockers = []
    if ram_gb > float(capacity.get("memory_available_gb") or 0) * .85:
        blockers.append(f"Healing needs approximately {ram_gb:.2f} GiB available RAM.")
    if disk_gb > capacity["disk_free_gb"]:
        blockers.append(f"A new healed checkpoint needs at least {disk_gb:.2f} GiB free disk space.")
    if settings["device"] != "cpu":
        index = int(settings["device"][5:])
        if not torch.cuda.is_available() or index >= torch.cuda.device_count():
            blockers.append("The selected accelerator is unavailable in this runtime.")
        else:
            free, _ = torch.cuda.mem_get_info(index)
            if training_gb > free / surgery.GIB * .85:
                blockers.append(f"Healing needs approximately {training_gb:.2f} GiB free accelerator memory.")
    return {"ready": not blockers, "blockers": blockers, "options": settings, "trainable_parameters": trainable,
            "estimated_ram_gb": round(ram_gb, 3), "estimated_training_gb": round(training_gb, 3),
            "estimated_disk_gb": round(disk_gb, 3), "resources": capacity,
            "train_bytes": train.stat().st_size, "eval_bytes": evaluation.stat().st_size,
            "note": "Estimates include float32 weights and AdamW state. Repeated data passes do not add unique training tokens."}


def text_blocks(path, tokenizer, length, check=lambda: None):
    pending = []
    with Path(path).open(encoding="utf-8") as stream:
        # read(size) bounds memory even if the input contains no line breaks.
        while text := stream.read(16384):
            check()
            pending.extend(tokenizer.encode(text, add_special_tokens=False))
            while len(pending) >= length:
                yield pending[:length]
                pending = pending[length:]
    if len(pending) >= 2:
        yield pending


def evaluate(model, tokenizer, path, length, batches, device, check):
    import torch
    model.eval()
    total, tokens, seen = 0.0, 0, 0
    with torch.inference_mode():
        for block in text_blocks(path, tokenizer, length, check):
            data = torch.tensor([block], device=device)
            loss = model(input_ids=data, labels=data, use_cache=False).loss
            if not torch.isfinite(loss):
                raise ValueError("Held-out evaluation returned non-finite loss.")
            total += loss.item() * (len(block) - 1)
            tokens += len(block) - 1
            seen += 1
            if seen >= batches:
                break
    if not tokens:
        raise ValueError("The evaluation file must contain at least two tokens.")
    return {"loss": total / tokens, "tokens": tokens, "blocks": seen}


def heal(source, destination, request, check=lambda: None, progress=lambda **kw: None):
    import torch
    settings = options(request)
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Healing output already exists.")
    train_file, eval_file = request["train_file"], request["eval_file"]
    check()
    train_hash, eval_hash = file_hash(train_file), file_hash(eval_file)
    if train_hash == eval_hash:
        raise ValueError("Training and evaluation files have identical contents. Use genuinely held-out text.")
    provenance = surgery.read_json(Path(source) / "model_surgery.json")
    progress(stage="loading", message="Loading expanded checkpoint")
    model, tokenizer = surgery.load_model(source)
    device = torch.device(settings["device"])
    model.to(device)
    model.config.use_cache = False
    if settings["train_scope"] == "inserted":
        model.requires_grad_(False)
        for index in provenance["inserted_layers"]:
            model.model.layers[index].requires_grad_(True)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    trainable = [p for p in model.parameters() if p.requires_grad]
    if not trainable:
        raise ValueError("No trainable expansion parameters were found.")
    trainable_count = sum(p.numel() for p in trainable)
    progress(stage="evaluating", message="Measuring held-out loss before healing")
    baseline = evaluate(model, tokenizer, eval_file, settings["sequence_length"], settings["eval_blocks"], device, check)
    optimizer = torch.optim.AdamW(trainable, lr=settings["learning_rate"], weight_decay=.01)
    optimizer.zero_grad(set_to_none=True)
    blocks = iter(text_blocks(train_file, tokenizer, settings["sequence_length"], check))
    consumed, repeats = 0, 0
    for step in range(settings["steps"]):
        check()
        model.train()
        total_loss = 0.0
        for _ in range(settings["accumulation"]):
            check()
            block = next(blocks, None)
            if block is None:
                repeats += 1
                blocks = iter(text_blocks(train_file, tokenizer, settings["sequence_length"], check))
                block = next(blocks, None)
                if block is None:
                    raise ValueError("The training file must contain at least two tokens.")
            data = torch.tensor([block], device=device)
            loss = model(input_ids=data, labels=data, use_cache=False).loss
            if not torch.isfinite(loss):
                raise ValueError("Training loss became non-finite. Parent checkpoints remain available.")
            total_loss += loss.item()
            (loss / settings["accumulation"]).backward()
            consumed += len(block) - 1
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        if not torch.isfinite(norm):
            raise ValueError("Training gradients became non-finite.")
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        progress(stage="training", message=f"Healing step {step + 1} of {settings['steps']}", step=step + 1,
                 steps=settings["steps"], loss=total_loss / settings["accumulation"], tokens=consumed, repeated_passes=repeats)
    check()
    progress(stage="evaluating", message="Measuring held-out loss after healing")
    result = evaluate(model, tokenizer, eval_file, settings["sequence_length"], settings["eval_blocks"], device, check)
    surgery.finite_weights(model)
    surgery.finite_probe(model, tokenizer)
    check()
    destination.mkdir(parents=True, exist_ok=False)
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.to("cpu")
    progress(stage="saving", message="Saving healed model to a new checkpoint")
    model.save_pretrained(destination, safe_serialization=True)
    tokenizer.save_pretrained(destination)
    # The last loss graph can retain parameter references after backward.
    # Release it before loading a second copy for serialization verification.
    del optimizer, trainable, model, loss, data
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    check()
    progress(stage="verifying", message="Reloading healed model")
    loaded, tokenizer = surgery.load_model(destination)
    surgery.finite_weights(loaded)
    surgery.finite_probe(loaded, tokenizer)
    provenance.update(status="trained_needs_quality_review", quality_validated=False,
                      trainable_parameters=trainable_count, training_tokens=consumed, repeated_passes=repeats,
                      before_evaluation=baseline, after_evaluation=result, loss_improved=result["loss"] < baseline["loss"],
                      train_sha256=train_hash, eval_sha256=eval_hash, healing_options=settings)
    surgery.write_json(destination / "model_surgery.json", provenance)
    return provenance
