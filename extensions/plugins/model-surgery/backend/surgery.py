# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Depth expansion for explicitly supported, local causal LM checkpoints."""

from __future__ import annotations

import copy
import gc
import json
import shutil
import uuid
from pathlib import Path


SUPPORTED = {"llama", "qwen2"}
GIB = 1024 ** 3


def integer(value, label, minimum=1):
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f"{label} must be an integer of at least {minimum}.") from error
    if isinstance(value, bool) or str(value).strip() != str(result) or result < minimum:
        raise ValueError(f"{label} must be an integer of at least {minimum}.")
    return result


def validate_config(config):
    if config.model_type not in SUPPORTED or getattr(config, "is_encoder_decoder", False):
        raise ValueError("Supported recipes: standard Llama and Qwen2 text causal LMs.")
    if getattr(config, "quantization_config", None):
        raise ValueError("Select an unquantized full SafeTensors model. Merge adapters before surgery.")
    if getattr(config, "use_sliding_window", False):
        raise ValueError("Sliding-window layer layouts need a separate tested recipe.")
    if any(kind != "full_attention" for kind in (getattr(config, "layer_types", None) or [])):
        raise ValueError("Hybrid or sliding-attention layer layouts need a separate tested recipe.")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.writing")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def hub_kwargs():
    try:
        from backend.hf_auth import get_huggingface_token
        token = get_huggingface_token()
        return {"token": token} if token else {}
    except ImportError:
        return {}


def configuration(source, revision="main"):
    from transformers import AutoConfig
    source = str(source).strip()
    if not source:
        raise ValueError("Choose a local model directory or a Hugging Face model ID.")
    kwargs = {"trust_remote_code": False, **hub_kwargs()}
    if Path(source).is_dir():
        if (Path(source) / "adapter_config.json").exists():
            raise ValueError("This is an adapter. Export a merged full model before surgery.")
        kwargs["local_files_only"] = True
    else:
        from huggingface_hub.utils import validate_repo_id
        validate_repo_id(source)
        kwargs["revision"] = revision
    config = AutoConfig.from_pretrained(source, **kwargs)
    validate_config(config)
    return config, str(getattr(config, "_commit_hash", None) or revision)


def resources(output_root):
    try:
        from backend.system_resources import detect_system_resources
        result = detect_system_resources()
    except ImportError:
        import psutil
        result = {"memory_available_gb": psutil.virtual_memory().available / GIB, "accelerators": []}
    result["disk_free_gb"] = shutil.disk_usage(output_root).free / GIB
    return result


def inspect(request, output_root):
    """Count architecture parameters on the meta device before loading weights."""
    import torch
    from transformers import AutoModelForCausalLM
    config, revision = configuration(request.get("source", ""), request.get("revision") or "main")
    first = integer(request.get("first", 0), "First layer", 0)
    count = integer(request.get("count", 1), "Block layers")
    copies = integer(request.get("copies", 1), "Additional copies")
    if first + count > config.num_hidden_layers:
        raise ValueError("The selected block extends past the model's last layer.")
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, trust_remote_code=False)
    base = sum(p.numel() for p in model.parameters())
    block = sum(p.numel() for layer in list(model.model.layers)[first:first + count] for p in layer.parameters())
    expanded = base + block * copies
    capacity = resources(output_root)
    # CPU float32 expansion, saving and reloading one model at a time.
    ram_gb, disk_gb = expanded * 4 / GIB * 1.6 + 1, expanded * 4 / GIB * 1.1 + .1
    blockers = []
    if ram_gb > float(capacity.get("memory_available_gb") or 0) * .85:
        blockers.append(f"Surgery needs approximately {ram_gb:.2f} GiB available RAM including headroom.")
    if disk_gb > capacity["disk_free_gb"]:
        blockers.append(f"The output needs at least {disk_gb:.2f} GiB free disk space.")
    return {"architecture": config.model_type, "source_layers": config.num_hidden_layers,
            "expanded_layers": config.num_hidden_layers + count * copies, "original_parameters": base,
            "expanded_parameters": expanded, "added_parameters": expanded - base,
            "first": first, "count": count, "copies": copies, "revision": revision,
            "estimated_ram_gb": round(ram_gb, 3), "estimated_disk_gb": round(disk_gb, 3),
            "resources": capacity, "blockers": blockers, "ready": not blockers,
            "context_limit": int(config.max_position_embeddings)}


def load_model(source):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    model, info = AutoModelForCausalLM.from_pretrained(str(source), local_files_only=True,
        trust_remote_code=False, use_safetensors=True, dtype=torch.float32, output_loading_info=True)
    if any(info.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
        raise ValueError("The checkpoint weights do not exactly match its architecture.")
    tokenizer = AutoTokenizer.from_pretrained(str(source), local_files_only=True, trust_remote_code=False)
    return model, tokenizer


def finite_probe(model, tokenizer):
    import torch
    model.eval()
    inputs = tokenizer("Language model verification.", return_tensors="pt")
    inputs.pop("token_type_ids", None)
    inputs = {key: value.to(next(model.parameters()).device) for key, value in inputs.items()}
    with torch.inference_mode():
        logits = model(**inputs, use_cache=False).logits
        if not torch.isfinite(logits).all():
            raise ValueError("The checkpoint produced non-finite logits.")
    return logits.detach().cpu()


def finite_weights(model):
    import torch
    for parameter in model.parameters():
        if not torch.isfinite(parameter).all():
            raise ValueError("The checkpoint contains non-finite weights.")


def layer_plan(depth: int, first: int, count: int, copies: int) -> list[int]:
    """Insert copies of a contiguous block immediately after that block."""
    depth, first, count, copies = integer(depth, "Source layers"), integer(first, "First layer", 0), integer(count, "Block layers"), integer(copies, "Copies")
    if first + count > depth:
        raise ValueError("Choose a nonempty block within the model and at least one copy.")
    block = list(range(first, first + count))
    return list(range(first + count)) + block * copies + list(range(first + count, depth))


def expand_model(model, first: int, count: int, copies: int, initialization="copy"):
    import torch

    config = model.config
    validate_config(config)
    if initialization not in {"copy", "identity"}:
        raise ValueError("Choose copied weights or identity initialization.")
    if getattr(model, "is_loaded_in_4bit", False) or getattr(model, "is_loaded_in_8bit", False) or getattr(config, "quantization_config", None):
        raise ValueError("Use an unquantized full model, not a quantized checkpoint.")
    layers = model.model.layers
    if len(layers) != config.num_hidden_layers:
        raise ValueError("The model layer count does not match its configuration.")
    plan = layer_plan(len(layers), first, count, copies)
    original = list(layers)
    # Reuse each original layer once; copies must own independent storage.
    seen = set()
    expanded = []
    for index in plan:
        duplicate = index in seen
        layer = copy.deepcopy(original[index]) if duplicate else original[index]
        if duplicate and initialization == "identity":
            with torch.no_grad():
                for projection in (layer.self_attn.o_proj, layer.mlp.down_proj):
                    projection.weight.zero_()
                    if projection.bias is not None:
                        projection.bias.zero_()
        expanded.append(layer)
        seen.add(index)
    for index, layer in enumerate(expanded):
        if hasattr(layer, "self_attn") and hasattr(layer.self_attn, "layer_idx"):
            layer.self_attn.layer_idx = index
    model.model.layers = torch.nn.ModuleList(expanded)
    if getattr(config, "layer_types", None) is not None:
        if len(config.layer_types) != len(original):
            raise ValueError("The layer-type configuration does not match the source depth.")
        config.layer_types = [config.layer_types[index] for index in plan]
    config.num_hidden_layers = len(expanded)
    return plan


def surgery(source: str, destination: str, first: int, count: int, copies: int,
            initialization="copy", check=lambda: None, progress=lambda **kw: None) -> dict:
    """Save and reload an expanded local model into a newly created directory."""
    import torch

    src = Path(source).resolve(strict=True)
    dst = Path(destination).resolve()
    if not src.is_dir() or dst.exists() or src == dst or src in dst.parents or dst in src.parents:
        raise ValueError("Select a local source directory and a new, separate output directory.")
    configuration(str(src))
    check()
    progress(stage="loading", message="Loading source SafeTensors on CPU")
    model, tokenizer = load_model(src)
    finite_weights(model)
    old_logits = finite_probe(model, tokenizer)
    before = sum(p.numel() for p in model.parameters())
    check()
    progress(stage="expanding", message="Creating independent layer copies")
    plan = expand_model(model, first, count, copies, initialization)
    identity_preserved = bool(torch.allclose(old_logits, finite_probe(model, tokenizer), atol=1e-5, rtol=1e-4))
    if initialization == "identity" and not identity_preserved:
        raise ValueError("Identity initialization did not preserve the source probe logits.")
    after = sum(p.numel() for p in model.parameters())
    check()
    dst.mkdir(parents=True, exist_ok=False)
    progress(stage="saving", message="Saving expanded checkpoint")
    model.save_pretrained(str(dst), safe_serialization=True)
    tokenizer.save_pretrained(str(dst))
    del model
    gc.collect()
    check()
    progress(stage="verifying", message="Reloading checkpoint and checking finite output")
    loaded, saved_tokenizer = load_model(dst)
    if len(loaded.model.layers) != len(plan) or sum(p.numel() for p in loaded.parameters()) != after:
        raise ValueError("Reloaded architecture or parameter count changed.")
    finite_weights(loaded)
    finite_probe(loaded, saved_tokenizer)
    evidence = {"original_parameters": before, "expanded_parameters": after,
                "layer_map": plan, "inserted_layers": list(range(first + count, first + count + count * copies)),
                "initialization": initialization, "status": "needs_healing", "reload_and_finite_logits": True,
                "identity_probe_preserved": identity_preserved, "quality_validated": False,
                "tool_owner": "Reallexi LLC", "tool_license": "Apache-2.0", "core_backlink": "https://llm.reallexi.io"}
    write_json(dst / "model_surgery.json", evidence)
    return evidence
