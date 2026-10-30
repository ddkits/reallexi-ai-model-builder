# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Isolated community surgery worker; checkpoints are published atomically."""
from __future__ import annotations

from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
surgery = importlib.import_module("extensions.plugins.model-surgery.backend.surgery")
healing = importlib.import_module("extensions.plugins.model-surgery.backend.healing")


class Cancelled(Exception):
    pass


@contextmanager
def worker_lock(root):
    with (Path(root) / "worker.lock").open("a+b") as stream:
        stream.write(b"0")
        stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("Another model surgery/healing worker is active.") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_job(job_dir):
    job_dir = Path(job_dir).resolve()
    request = surgery.read_json(job_dir / "request.json")
    state = surgery.read_json(job_dir / "status.json")
    def check():
        if (job_dir / "cancel").exists():
            raise Cancelled("Cancellation completed. Parent checkpoints are preserved.")
    def progress(**changes):
        check()
        state.update(changes, updated_at=time.time())
        surgery.write_json(job_dir / "status.json", state)
    try:
        with worker_lock(job_dir.parent):
            progress(status="running", stage="preflight", message="Checking current resources", pid=os.getpid())
            if request["operation"] == "expand":
                plan = surgery.inspect(request, job_dir)
                if not plan["ready"]:
                    raise ValueError(" ".join(plan["blockers"]))
                progress(stage="downloading", message="Resolving source weights at the reviewed revision")
                if Path(request["source"]).is_dir():
                    source = request["source"]
                else:
                    from huggingface_hub import snapshot_download
                    source = snapshot_download(request["source"], revision=plan["revision"], **surgery.hub_kwargs(),
                        allow_patterns=["config.json", "generation_config.json", "*.safetensors", "*.safetensors.index.json",
                            "tokenizer*", "special_tokens_map.json", "vocab.json", "vocab.txt", "merges.txt", "added_tokens.json"])
                check()
                evidence = surgery.surgery(str(source), str(job_dir / "partial"), plan["first"], plan["count"], plan["copies"],
                    request.get("initialization", "identity"), check, progress)
                evidence.update(source=request["source"], source_revision=plan["revision"])
            elif request["operation"] == "heal":
                plan = healing.preflight(request, job_dir)
                if not plan["ready"]:
                    raise ValueError(" ".join(plan["blockers"]))
                evidence = healing.heal(request["source"], job_dir / "partial", request, check, progress)
            else:
                # Keep prompt tests in the same resource-isolated worker queue.
                plugin = importlib.import_module("extensions.plugins.model-surgery.backend.plugin")
                plan = plugin.probe_preflight(request, job_dir)
                if not plan["ready"]:
                    raise ValueError(" ".join(plan["blockers"]))
                progress(stage="testing", message="Generating a deterministic prompt sample on CPU")
                import torch
                from transformers import StoppingCriteria, StoppingCriteriaList
                class CheckCancellation(StoppingCriteria):
                    def __call__(self, input_ids, scores, **kwargs):
                        check()
                        return False
                model, tokenizer = surgery.load_model(request["source"])
                model.eval()
                inputs = tokenizer(request["prompt"], return_tensors="pt")
                inputs.pop("token_type_ids", None)
                with torch.inference_mode():
                    output = model.generate(**inputs, max_new_tokens=request["max_new_tokens"], do_sample=False,
                        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
                        stopping_criteria=StoppingCriteriaList([CheckCancellation()]))
                evidence = {"prompt": request["prompt"], "completion": tokenizer.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True),
                            "quality_validated": False}
                check()
                state.update(status="completed", stage="completed", message="Prompt sample ready for review", evidence=evidence, updated_at=time.time())
                surgery.write_json(job_dir / "status.json", state)
                return
            check()
            surgery.write_json(job_dir / "partial" / "model_surgery.json", evidence)
            (job_dir / "partial").rename(job_dir / "model")
            # Commit completion before a late cancellation can alter the state.
            state.update(status="completed", stage="completed", message="Checkpoint verified", evidence=evidence,
                         model_path=str(job_dir / "model"), updated_at=time.time())
            surgery.write_json(job_dir / "status.json", state)
    except Exception as error:
        state.update(status="cancelled" if isinstance(error, Cancelled) else "failed", stage="stopped",
                     message=str(error), updated_at=time.time())
        surgery.write_json(job_dir / "status.json", state)
        if not isinstance(error, Cancelled):
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_job(sys.argv[1])
