# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Bounded-memory raw-text continual pre-training for expanded checkpoints."""
from __future__ import annotations

import gc
import hashlib
import importlib
import math
import shutil
from pathlib import Path

surgery = importlib.import_module("extensions.plugins.model-surgery.backend.surgery")
phases = importlib.import_module("extensions.plugins.model-surgery.backend.phases")


def options(request):
    result = {"steps": surgery.integer(request.get("steps", 100), "Optimizer steps"),
              "sequence_length": surgery.integer(request.get("sequence_length", 256), "Sequence length", 2),
              "accumulation": surgery.integer(request.get("accumulation", 1), "Gradient accumulation"),
              "eval_blocks": surgery.integer(request.get("eval_blocks", 8), "Evaluation blocks")}
    rate = float(request.get("learning_rate", 1e-5))
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Learning rate must be finite and positive.")
    result.update(learning_rate=rate, train_scope=str(request.get("train_scope") or "inserted"),
                  device=str(request.get("device") or "cpu"), optimizer=str(request.get("optimizer") or "auto"))
    if result["optimizer"] not in {"auto", "adamw", "adamw8bit", "disk_adamw"}:
        raise ValueError("Choose automatic smart phases, standard AdamW, 8-bit state, or disk-backed AdamW.")
    if result["train_scope"] not in {"inserted", "full"}:
        raise ValueError("Train inserted layers or the full model.")
    device = result["device"]
    if device != "cpu" and not (device.startswith("cuda:") and device[5:].isdigit()):
        raise ValueError("Select CPU or a detected CUDA/ROCm device.")
    if result["optimizer"] == "adamw8bit" and device == "cpu":
        raise ValueError("This 8-bit AdamW recipe requires a detected NVIDIA CUDA device. Use standard AdamW on CPU.")
    return result


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_data(request):
    train, evaluation = Path(request["train_file"]), Path(request["eval_file"])
    for path in (train, evaluation):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md"} or path.stat().st_size == 0:
            raise ValueError("Use nonempty UTF-8 .txt or .md files for training and held-out evaluation.")
    if train.resolve() == evaluation.resolve():
        raise ValueError("Use a separate held-out evaluation file.")
    if not request.get("data_rights_confirmed"):
        raise ValueError("Confirm that you have permission to train on the selected text.")
    return train, evaluation


def preflight(request, output_root, expansion=None):
    import torch
    config, _ = surgery.configuration(request["source"], request.get("revision", "main"))
    settings = options(request)
    if settings["sequence_length"] > config.max_position_embeddings:
        raise ValueError("Sequence length exceeds the model context window.")
    evidence = expansion or surgery.read_json(Path(request["source"]) / "model_surgery.json")
    train, evaluation = validate_data(request)
    total = evidence["expanded_parameters"]
    added = total - evidence["original_parameters"]
    trainable = added if settings["train_scope"] == "inserted" else total
    layers = expansion["expanded_layers"] if expansion else config.num_hidden_layers
    activation = layers * config.hidden_size * settings["sequence_length"] * 64 / surgery.GIB
    capacity = surgery.resources(output_root)
    requested_device = settings["device"]
    free_gb, total_vram_gb = 0.0, 0.0
    if requested_device != 'cpu' and torch.cuda.is_available() and int(requested_device[5:]) < torch.cuda.device_count():
        free, device_total = torch.cuda.mem_get_info(int(requested_device[5:]))
        free_gb, total_vram_gb = free/surgery.GIB, device_total/surgery.GIB
    has_8bit = False
    if requested_device != 'cpu' and getattr(torch.version,'cuda',None):
        try:
            import bitsandbytes as bnb
            has_8bit = hasattr(bnb.optim,'AdamW8bit')
        except (ImportError,OSError,RuntimeError):
            pass
    largest = config.hidden_size*max(config.vocab_size,config.intermediate_size,config.hidden_size)
    settings['optimizer'],settings['device'],training_gb = phases.training_strategy(total,trainable,activation,largest,settings['optimizer'],requested_device,float(capacity.get('memory_available_gb') or 0),free_gb,has_8bit)
    ram_gb = max(total * 4 / surgery.GIB * 1.6 + 1, training_gb if settings["device"] == "cpu" else 0)
    disk_gb = total * 4 / surgery.GIB * 1.1 + .1
    optimizer_disk_gb = trainable*12/surgery.GIB*1.05 if settings['optimizer']=='disk_adamw' else 0
    blockers = []
    if settings["optimizer"] == "adamw8bit":
        try:
            import bitsandbytes as bnb
            if not hasattr(bnb.optim, "AdamW8bit") or not getattr(torch.version, "cuda", None):
                blockers.append("8-bit AdamW needs bitsandbytes and an NVIDIA CUDA-enabled runtime.")
        except (ImportError, OSError, RuntimeError) as error:
            blockers.append(f"8-bit AdamW is unavailable in this runtime: {error}. Update the runtime or select standard AdamW.")
    available_ram = float(capacity.get("memory_available_gb") or 0)
    # The loading estimate already includes 60% headroom plus 1 GiB;
    # execution strategies also reserve working buffers. Do not reserve twice.
    if ram_gb > available_ram:
        blockers.append(f"Healing needs about {ram_gb:.2f} GiB backend RAM including headroom; {available_ram:.2f} GiB is available of {float(capacity.get('memory_total_gb') or 0):.2f} GiB visible to this runtime. Windows host RAM and GPU memory are separate; Docker/WSL may expose less than installed RAM.")
    combined_disk_gb = disk_gb + optimizer_disk_gb + (disk_gb if expansion else 0)
    if combined_disk_gb > capacity["disk_free_gb"]:
        blockers.append(f"Checkpoints and phased optimizer workspace need at least {combined_disk_gb:.2f} GiB free disk space.")
    if settings["device"] != "cpu":
        index = int(settings["device"][5:])
        if not torch.cuda.is_available() or index >= torch.cuda.device_count():
            blockers.append("The selected accelerator is unavailable in this runtime.")
        else:
            free, _ = torch.cuda.mem_get_info(index)
            if training_gb > free / surgery.GIB * .85:
                blockers.append(f"Selected execution needs about {training_gb:.2f} GiB GPU memory including working buffers; {free_gb:.2f} GiB is free of {total_vram_gb:.2f} GiB total. Host RAM is separate. Automatic smart phases can try disk-backed state or CPU execution while preserving scope.")
    return {"ready": not blockers, "blockers": blockers, "options": settings, "trainable_parameters": trainable,
            "estimated_ram_gb": round(ram_gb, 3), "ram_headroom_included": True, "estimated_training_gb": round(training_gb, 3),
            "estimated_disk_gb": round(combined_disk_gb - optimizer_disk_gb, 3), "resources": capacity,
            "optimizer_disk_gb": round(optimizer_disk_gb,3), "available_accelerator_gb": round(free_gb,3),
            "total_accelerator_gb": round(total_vram_gb,3), "requested_device": requested_device,
            "smart_phases": {"optimizer":settings['optimizer'],"device":settings['device'],"checkpoint_shard_mib":256,"optimizer_buffer_mib":4,"scope_preserved":True},
            "train_bytes": train.stat().st_size, "eval_bytes": evaluation.stat().st_size,
            "note": "Estimates include float32 weights, gradients, and the selected optimizer state. 8-bit AdamW quantizes optimizer state, not model weights. Repeated data passes do not add unique training tokens."}


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


def heal(source, destination, request, check=lambda: None, progress=lambda **kw: None, source_baseline=None):
    import torch
    destination = Path(destination)
    reviewed = preflight(request, destination.parent)
    if not reviewed['ready']:
        raise ValueError(' '.join(reviewed['blockers']))
    settings = reviewed['options']
    if destination.exists():
        raise ValueError("Healing output already exists.")
    train_file, eval_file = request["train_file"], request["eval_file"]
    check()
    train_hash, eval_hash = file_hash(train_file), file_hash(eval_file)
    if train_hash == eval_hash:
        raise ValueError("Training and evaluation files have identical contents. Use genuinely held-out text.")
    provenance = surgery.read_json(Path(source) / "model_surgery.json")
    provenance.pop("source_evaluation", None)
    if source_baseline:
        if source_baseline["eval_sha256"] != eval_hash:
            raise ValueError("The evaluation file changed after measuring source loss.")
        provenance["source_evaluation"] = source_baseline["evaluation"]
    progress(stage="loading", message="Loading expanded checkpoint")
    model, tokenizer = surgery.load_model(source)
    model.config.model_name = surgery.lexi_name(provenance["expanded_parameters"])
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
    if settings["optimizer"] == "disk_adamw":
        optimizer = phases.DiskAdamW(trainable,destination.with_name(destination.name+'.optimizer-work'),lr=settings['learning_rate'],check=check)
    elif settings["optimizer"] == "adamw8bit":
        import bitsandbytes as bnb
        optimizer = bnb.optim.AdamW8bit(trainable, lr=settings["learning_rate"], weight_decay=.01)
    else:
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
        norm = optimizer.clip_grad_norm(1.0) if settings['optimizer']=='disk_adamw' else torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        if not torch.isfinite(norm):
            raise ValueError("Training gradients became non-finite.")
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        progress(stage="training", message=f"Healing step {step + 1} of {settings['steps']}", step=step + 1,
                 steps=settings["steps"], loss=total_loss / settings["accumulation"], tokens=consumed, repeated_passes=repeats)
    check()
    progress(stage="evaluating", message="Measuring held-out loss after healing")
    result = evaluate(model, tokenizer, eval_file, settings["sequence_length"], settings["eval_blocks"], device, check)
    if file_hash(eval_file) != eval_hash or file_hash(train_file) != train_hash:
        raise ValueError("Training or evaluation text changed during healing.")
    surgery.finite_weights(model)
    surgery.finite_probe(model, tokenizer)
    check()
    destination.mkdir(parents=True, exist_ok=False)
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.to("cpu")
    progress(stage="saving", message="Saving healed model to a new checkpoint")
    importlib.import_module("extensions.plugins.model-surgery.backend.phases").save_checkpoint(model, destination)
    tokenizer.save_pretrained(destination)
    if settings['optimizer']=='disk_adamw':
        optimizer.close()
    for filename in ("LICENSE", "LICENSE.txt", "LICENSE.md", "NOTICE", "COPYRIGHT.md"):
        if (Path(source) / filename).is_file():
            shutil.copy2(Path(source) / filename, destination / filename)
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
    provenance.update(surgery.ATTRIBUTION, model_name=surgery.lexi_name(provenance["expanded_parameters"]),
                      base_model_type=loaded.config.model_type,
                      status="trained_needs_quality_review", quality_validated=False,
                      trainable_parameters=trainable_count, training_tokens=consumed, repeated_passes=repeats,
                      before_evaluation=baseline, after_evaluation=result, loss_improved=result["loss"] < baseline["loss"],
                      train_sha256=train_hash, eval_sha256=eval_hash, healing_options=settings)
    surgery.write_json(destination / "model_surgery.json", provenance)
    surgery.model_card(destination, provenance)
    return provenance
