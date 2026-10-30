# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Local-admin community Model Surgery extension routes."""
from __future__ import annotations

import ctypes
from contextlib import closing
import importlib
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

MODULE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_ROOT.parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
surgery = importlib.import_module("extensions.plugins.model-surgery.backend.surgery")
healing = importlib.import_module("extensions.plugins.model-surgery.backend.healing")
inventory = importlib.import_module("extensions.plugins.model-surgery.backend.inventory")

DATA_ROOT = PROJECT_ROOT / "backend/data"
STORE = DATA_ROOT / "model-surgery"


def model_library(directory=None):
    return inventory.discover(PROJECT_ROOT, DATA_ROOT, STORE, directory)


def job_path(value):
    value = str(value)
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Invalid surgery job ID.")
    return STORE / value


def process_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def job_status(directory):
    state = surgery.read_json(directory / "status.json")
    if state["status"] in {"queued", "running"}:
        process_file = directory / "process.json"
        pid = state.get("pid") or (surgery.read_json(process_file).get("pid") if process_file.exists() else None)
        if pid and not process_alive(pid):
            # A worker can exit between reading status and probing the PID.
            state = surgery.read_json(directory / "status.json")
            if state["status"] in {"queued", "running"}:
                state.update(status="failed", stage="interrupted", message="Worker exited before checkpoint verification. Create a new run; parent checkpoints are preserved.")
                surgery.write_json(directory / "status.json", state)
    return state


def jobs():
    STORE.mkdir(parents=True, exist_ok=True)
    result = []
    for path in STORE.iterdir():
        if path.is_dir() and re.fullmatch(r"[0-9a-f]{32}", path.name) and (path / "status.json").exists():
            result.append(job_status(path))
    return sorted(result, key=lambda item: item["created_at"], reverse=True)


def normalize(body):
    operation = body.get("operation") or "expand"
    if operation not in {"expand", "heal", "probe"}:
        raise ValueError("Choose expansion, healing, or a prompt test.")
    if operation == "expand":
        return {"operation": operation, "source": str(body.get("source") or "").strip(),
                "revision": str(body.get("revision") or "main").strip(),
                "first": surgery.integer(body.get("first", 0), "First layer", 0),
                "count": surgery.integer(body.get("count", 1), "Block layers"),
                "copies": surgery.integer(body.get("copies", 1), "Additional copies"),
                "initialization": str(body.get("initialization") or "identity")}
    parent = job_status(job_path(body.get("parent_id")))
    if parent["status"] != "completed":
        raise ValueError("Select a completed, verified surgery checkpoint first.")
    if parent["operation"] == "probe":
        raise ValueError("Select a checkpoint, rather than a prompt-test result.")
    if operation == "probe":
        prompt = str(body.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("Enter a test prompt.")
        return {"operation": operation, "parent_id": parent["id"], "source": parent["model_path"],
                "prompt": prompt, "max_new_tokens": surgery.integer(body.get("max_new_tokens", 64), "New tokens")}
    request = {"operation": operation, "parent_id": parent["id"], "source": parent["model_path"],
               "train_file": str(body.get("train_file") or "").strip(), "eval_file": str(body.get("eval_file") or "").strip(),
               "data_rights_confirmed": body.get("data_rights_confirmed") is True, **healing.options(body)}
    return request


def preflight(body):
    STORE.mkdir(parents=True, exist_ok=True)
    request = normalize(body)
    if request["operation"] == "expand":
        if request["initialization"] not in {"identity", "copy"}:
            raise ValueError("Choose identity or copied initialization.")
        plan = surgery.inspect(request, STORE)
        request["revision"] = plan["revision"]
    elif request["operation"] == "heal":
        plan = healing.preflight(request, STORE)
    else:
        plan = probe_preflight(request, STORE)
    return {"request": request, "plan": plan}


def probe_preflight(request, root):
    config, _ = surgery.configuration(request["source"])
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(request["source"], local_files_only=True, trust_remote_code=False)
    length = len(tokenizer.encode(request["prompt"]))
    if length + request["max_new_tokens"] > config.max_position_embeddings:
        raise ValueError("Prompt plus output exceeds the model context window. Shorten the prompt or output.")
    evidence = surgery.read_json(Path(request["source"]) / "model_surgery.json")
    capacity = surgery.resources(root)
    ram_gb = evidence["expanded_parameters"] * 4 / surgery.GIB * 1.6 + 1
    blockers = [] if ram_gb <= capacity.get("memory_available_gb", 0) * .85 else [f"Prompt testing needs about {ram_gb:.2f} GiB available RAM."]
    return {"ready": not blockers, "blockers": blockers, "estimated_ram_gb": ram_gb, "resources": capacity}


def refuse_active_training():
    database = DATA_ROOT / "ai_model_builder.db"
    if database.exists():
        with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
            table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_jobs'").fetchone()
            if table and connection.execute("SELECT 1 FROM training_jobs WHERE status='running' LIMIT 1").fetchone():
                raise ValueError("A core training job is running. Finish or pause it before starting model surgery/healing.")


def create_job(body):
    if any(job["status"] in {"queued", "running"} for job in jobs()):
        raise ValueError("A surgery/healing job is already active. Wait or request cancellation first.")
    refuse_active_training()
    reviewed = preflight(body)
    if not reviewed["plan"]["ready"]:
        raise ValueError(" ".join(reviewed["plan"]["blockers"]))
    request = reviewed["request"]
    identifier = uuid.uuid4().hex
    directory = job_path(identifier)
    directory.mkdir(exist_ok=False)
    state = {"id": identifier, "operation": request["operation"], "status": "queued", "stage": "queued",
             "created_at": time.time(), "message": "Starting isolated worker", "parent_id": request.get("parent_id"),
             "source": request["source"], "plan": reviewed["plan"]}
    surgery.write_json(directory / "request.json", request)
    surgery.write_json(directory / "status.json", state)
    try:
        with (directory / "worker.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, str(MODULE_ROOT / "worker.py"), str(directory)],
                cwd=str(PROJECT_ROOT), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        surgery.write_json(directory / "process.json", {"pid": process.pid})
        # Hold the Popen object until exit and reap children on POSIX.
        threading.Thread(target=process.wait, name=f"model-surgery-{identifier[:8]}", daemon=True).start()
    except Exception as error:
        state.update(status="failed", message=f"Worker could not start: {error}")
        surgery.write_json(directory / "status.json", state)
        raise
    return state


def save_dataset(body):
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Choose a nonempty UTF-8 text or Markdown file.")
    if len(text.encode("utf-8")) > 16 * 1024 * 1024:
        raise ValueError("For files larger than 16 MiB, use a mounted local file path.")
    directory = STORE / "datasets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}.txt"
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "bytes": path.stat().st_size}


def run_api_route(payload, context):
    # Authentication and local-only enforcement are provided by the core route.
    body = payload.get("body") or {}
    route = context.get("unit_id", "").rsplit(".", 1)[-1]
    if route == "catalog":
        STORE.mkdir(parents=True, exist_ok=True)
        return {"architectures": sorted(surgery.SUPPORTED), "resources": surgery.resources(STORE),
                "jobs": jobs(), "model_library": model_library(),
                "help_url": "https://github.com/ddkits/reallexi-ai-model-builder/blob/main/docs/MODEL_SURGERY.md"}
    if route in {"models-list", "models-scan"}:
        return model_library(body.get("directory"))
    if route == "jobs-list":
        return {"jobs": jobs()}
    if route == "preflight":
        return preflight(body)
    if route == "jobs-create":
        return {"job": create_job(body)}
    if route == "dataset":
        return save_dataset(body)
    if route == "cancel":
        directory = job_path(body.get("id"))
        state = job_status(directory)
        if state["status"] in {"queued", "running"}:
            (directory / "cancel").touch(exist_ok=True)
        return {"job": state, "message": "Cancellation is checked between load/save stages and training microsteps. Completed checkpoints remain available."}
    raise ValueError("Unknown Model Surgery route.")
