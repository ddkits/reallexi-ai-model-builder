# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Read-only model discovery. Never load weights, download, or execute models."""
from __future__ import annotations

from collections import deque
from contextlib import closing
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3

SUPPORTED = importlib.import_module("extensions.plugins.model-surgery.backend.surgery").SUPPORTED
MAX_METADATA_BYTES = 4 * 1024 * 1024
SCAN_DIRECTORIES = 3000
SCAN_DEPTH = 5


def metadata(path):
    try:
        if path.stat().st_size > MAX_METADATA_BYTES:
            return {}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def nonempty(path):
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def assess(path):
    result = {"available": path.exists(), "eligible": False, "architecture": "", "reason": ""}
    def reject(reason):
        return {**result, "reason": reason}
    if not result["available"]:
        return reject("Checkpoint folder is missing or is not mounted in this backend.")
    if path.suffix.lower() == ".gguf" and path.is_file():
        return reject("GGUF inference export. Select the original full SafeTensors checkpoint for surgery.")
    if not path.is_dir():
        return reject("Select a full model directory, including its configuration and tokenizer.")
    if (path / "adapter_config.json").is_file():
        return reject("Adapter only. Build a merged full SafeTensors model in Trained Models, then refresh this list.")
    if (path / "model_index.json").is_file():
        return reject("Media pipeline. This surgery recipe supports Llama and Qwen2 text causal models.")
    config = metadata(path / "config.json")
    if not config:
        return reject("Model configuration is missing or unreadable. Select a complete model folder.")
    result["architecture"] = str(config.get("model_type") or "")
    if result["architecture"] not in SUPPORTED or config.get("is_encoder_decoder"):
        return reject(f"Architecture {result['architecture'] or 'unknown'} is not supported by the Llama/Qwen2 text recipe.")
    if config.get("quantization_config"):
        return reject("Quantized checkpoint. Select the original unquantized full model.")
    layer_types = config.get("layer_types") or []
    if not isinstance(layer_types, list) or config.get("use_sliding_window") or any(kind != "full_attention" for kind in layer_types):
        return reject("Hybrid or sliding-attention layout needs a separately tested surgery recipe.")
    index_file = path / "model.safetensors.index.json"
    if index_file.exists():
        weight_map = metadata(index_file).get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            return reject("SafeTensors shard index is missing or invalid.")
        shards = set()
        for name in weight_map.values():
            if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts or not name.endswith(".safetensors"):
                return reject("SafeTensors download is incomplete: one or more indexed shards are missing.")
            if name not in shards and not nonempty(path / name):
                return reject("SafeTensors download is incomplete: one or more indexed shards are missing.")
            shards.add(name)
    elif not any(nonempty(file) for file in path.glob("*.safetensors")):
        return reject("Full SafeTensors weights are missing. Finish the download or export SafeTensors first.")
    if not any(nonempty(path / name) for name in ("tokenizer.json", "tokenizer.model", "spiece.model", "vocab.json", "vocab.txt")):
        return reject("Tokenizer files are missing. Select a complete model with its tokenizer.")
    return {**result, "eligible": True, "reason": "Ready for architecture and resource preflight. Weights are verified when the worker runs."}


def registered_jobs(data_root, warnings):
    database = data_root / "ai_model_builder.db"
    if not database.is_file():
        return []
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
            connection.row_factory = sqlite3.Row
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_jobs'").fetchone():
                return []
            return [dict(row) for row in connection.execute("SELECT id,name,status FROM training_jobs ORDER BY id DESC")]
    except sqlite3.Error:
        warnings.append("Training history could not be read right now. Refresh after the database is available.")
        return []


def default_local_roots(project_root, data_root):
    roots = [("Mounted local inputs", project_root / "local-inputs"), ("Local models", project_root / "models"),
             ("Stored models", data_root / "models"), ("Local exports", data_root / "exports")]
    for directory in str(os.getenv("REALLEXI_MODEL_SURGERY_MODEL_DIRS", "")).split(os.pathsep):
        if directory.strip():
            roots.append(("Configured model folder", Path(directory.strip()).expanduser()))
    # Discover extension-owned artifacts by storage convention, without
    # importing private plugins or scanning credentials, uploads, or datasets.
    if data_root.is_dir():
        for child in sorted(data_root.iterdir()):
            if child.is_dir() and not child.is_symlink() and (child / "artifacts").is_dir():
                roots.append(("Extension model artifacts", child / "artifacts"))
    return roots


def default_hub_roots(data_root):
    from huggingface_hub.constants import HF_HUB_CACHE
    return [Path(HF_HUB_CACHE), data_root / "huggingface/hub"]


def discover(project_root, data_root, store, directory=None, *, local_roots=None, hub_roots=None):
    project_root, data_root, store = Path(project_root), Path(data_root), Path(store)
    models, roots, warnings, seen = [], [], [], set()
    def add(path, kind, label, job_id=None, reason=None):
        try:
            path = path.resolve()
            details = assess(path)
        except (OSError, ValueError, TypeError, RuntimeError):
            details = {"available": False, "eligible": False, "architecture": "", "reason": "Checkpoint metadata could not be inspected. Check the folder's access and configuration."}
        key = os.path.normcase(str(path))
        if key in seen:
            return
        seen.add(key)
        if reason:
            details.update(eligible=False, reason=reason)
        models.append({"id": hashlib.sha256(key.encode()).hexdigest()[:24], "kind": kind, "label": label,
                       "path": str(path), "job_id": job_id, **details})
    def record_root(label, path):
        roots.append({"label": label, "path": str(path.resolve()), "available": path.is_dir()})

    record_root("Trained model artifacts", data_root / "artifacts")
    jobs = registered_jobs(data_root, warnings)
    for job in jobs:
        if job["status"] != "completed":
            continue
        job_id = int(job["id"])
        artifact = data_root / "artifacts" / f"job_{job_id}"
        manifest = metadata(artifact / "manifest.json")
        kind = manifest.get("artifact_type")
        folder = artifact / ("adapter" if kind == "lora_adapter" else "model")
        reason = None
        if kind == "rag_index":
            folder, reason = artifact, "RAG index. It has no Transformer weights to expand."
        elif (manifest.get("numerical_validation") or {}).get("valid") is False:
            reason = "This artifact failed numerical validation. Use a healthy checkpoint instead."
        add(folder, "trained", f"{job['name']} · job #{job_id}", job_id, reason)

    names = {int(job["id"]): job["name"] for job in jobs}
    exports = data_root / "model_exports"
    record_root("Merged SafeTensors exports", exports)
    if exports.is_dir():
        for job_dir in sorted(exports.glob("job_*")):
            if not job_dir.name.removeprefix("job_").isdigit():
                continue
            job_id = int(job_dir.name.removeprefix("job_"))
            formats = metadata(job_dir / "export-state.json").get("formats") or {}
            for folder, state_key in (("standalone", "standalone"), ("custom-standalone", "custom-standalone")):
                path = job_dir / folder
                if not path.is_dir():
                    continue
                status = (formats.get(state_key) or {}).get("status")
                reason = None if status in {None, "ready", "completed"} else f"Export is {status}. Finish or rebuild the SafeTensors export, then refresh."
                add(path, "merged", f"{names.get(job_id, 'Trained model')} · job #{job_id} · {'custom merge' if folder.startswith('custom') else 'merged SafeTensors'}", job_id, reason)

    record_root("Surgery checkpoints", store)
    if store.is_dir():
        for job_dir in sorted(store.iterdir()):
            if not job_dir.is_dir() or not (job_dir / "status.json").is_file():
                continue
            state = metadata(job_dir / "status.json")
            if state.get("status") == "completed" and state.get("operation") in {"expand", "heal"}:
                add(job_dir / "model", "surgery", f"{'Healed' if state['operation'] == 'heal' else 'Expanded'} checkpoint · {job_dir.name[:8]}")

    def scan(root, label):
        root = root.resolve()
        record_root(label, root)
        if not root.is_dir():
            return
        if root == Path(root.anchor) or root == Path.home().resolve():
            warnings.append(f"{label} points to an entire drive or home. Choose a specific model folder instead.")
            return
        queue, visited = deque([(root, 0)]), set()
        while queue and len(visited) < SCAN_DIRECTORIES:
            current, depth = queue.popleft()
            try:
                current = current.resolve()
                if current in visited or not current.is_relative_to(root):
                    continue
                visited.add(current)
                entries = list(current.iterdir())
                files = {entry.name for entry in entries if entry.is_file()}
                if files & {"config.json", "adapter_config.json", "model_index.json"} or any(name.endswith(".safetensors") for name in files):
                    add(current, "local", f"{current.name} · {label}")
                    continue
                for entry in entries:
                    if entry.is_file() and entry.suffix.lower() == ".gguf":
                        add(entry, "local", f"{entry.stem} · GGUF")
                    elif depth < SCAN_DEPTH and entry.is_dir() and not entry.is_symlink() and entry.name not in {".git", "__pycache__", "node_modules", "blobs"}:
                        queue.append((entry, depth + 1))
            except OSError:
                warnings.append(f"A model folder in {label} could not be read.")
        if queue:
            warnings.append(f"Scan of {label} reached its directory budget. Scan a more specific model folder to find deeper entries.")
    local = list(default_local_roots(project_root, data_root) if local_roots is None else local_roots)
    if not jobs and (data_root / "artifacts").is_dir():
        local.append(("Local training artifacts", data_root / "artifacts"))
    if directory:
        custom = Path(str(directory).strip()).expanduser()
        if not custom.is_dir():
            raise ValueError("That model folder does not exist in the backend. Mount host folders before scanning them.")
        custom = custom.resolve()
        if custom == Path(custom.anchor) or custom == Path.home().resolve():
            raise ValueError("Choose a specific model folder, rather than an entire drive or home directory.")
        local.append(("Selected model folder", custom))
    scanned = set()
    for label, root in local:
        if root.resolve() not in scanned:
            scanned.add(root.resolve())
            scan(root, label)
    for hub in default_hub_roots(data_root) if hub_roots is None else hub_roots:
        hub = Path(hub).resolve()
        if hub in scanned:
            continue
        scanned.add(hub)
        record_root("Downloaded Hugging Face models", hub)
        if not hub.is_dir():
            continue
        for repo in sorted(hub.glob("models--*")):
            for snapshot in sorted((repo / "snapshots").glob("*")):
                if snapshot.is_dir():
                    add(snapshot, "cached", f"{repo.name.removeprefix('models--').replace('--', '/')} · cached {snapshot.name[:8]}")
    return {"models": models, "roots": roots, "warnings": list(dict.fromkeys(warnings)),
            "eligible_count": sum(model["eligible"] for model in models),
            "note": "Discovery reads model metadata only. Other host folders must be mounted or scanned explicitly; no weights are loaded or downloaded."}
