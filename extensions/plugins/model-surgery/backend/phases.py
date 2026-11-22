# SPDX-FileCopyrightText: 2026 Reallexi LLC
# SPDX-License-Identifier: Apache-2.0
"""Bounded checkpoint I/O and full-parameter AdamW with disk-backed state.

Data windows alone do not reduce resident model state. This optimizer spools
gradients as backward produces them, then clips globally and updates every
selected parameter using bounded CPU buffers and disk-backed Adam moments.
"""
from __future__ import annotations

import json
import math
import inspect
from pathlib import Path

CHECKPOINT_SHARD_BYTES = 256 * 1024**2
BUFFER_BYTES = 4 * 1024**2


def save_checkpoint(model, destination):
    parameters = inspect.signature(model.save_pretrained).parameters.values()
    supported = any(parameter.name == 'max_shard_size' or parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters)
    options = {'safe_serialization':True, **({'max_shard_size':CHECKPOINT_SHARD_BYTES} if supported else {})}
    model.save_pretrained(destination, **options)


def training_strategy(total, trainable, activation_gb, largest_parameters, requested, device, ram_gb, vram_gb, has_8bit):
    """Keep scope/work unchanged; trade optimizer storage and execution speed."""
    gib = 1024**3
    def memory(optimizer):
        if optimizer == 'disk_adamw':
            return (total+largest_parameters)*4/gib+activation_gb+1.25
        return (total*4+trainable*(7 if optimizer=='adamw8bit' else 12))/gib+activation_gb+1
    candidates = [requested] if requested != 'auto' else ['adamw']+(['adamw8bit'] if device!='cpu' and has_8bit else [])+['disk_adamw']
    # CPU estimates already include fixed working headroom. Keep the extra
    # accelerator reserve for CUDA allocations without double-reserving RAM.
    budget = ram_gb if device=='cpu' else vram_gb*.85
    for optimizer in candidates:
        if memory(optimizer)<=budget:
            return optimizer,device,memory(optimizer)
    if requested=='auto' and device!='cpu':
        for optimizer in ['adamw','disk_adamw']:
            if memory(optimizer)<=ram_gb:
                return optimizer,'cpu',memory(optimizer)
    return candidates[-1],device,memory(candidates[-1])


class DiskAdamW:
    def __init__(self, parameters, directory, lr, weight_decay=.01, betas=(.9,.999), eps=1e-8, check=lambda: None):
        self.parameters = list(parameters)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.lr, self.weight_decay, self.betas, self.eps, self.check = lr, weight_decay, betas, eps, check
        self.chunk_elements = BUFFER_BYTES // 4
        self.indices, self.steps, self.coefficient = set(), {}, 1.0
        self.handles = [parameter.register_post_accumulate_grad_hook(lambda parameter, index=index: self.capture(parameter,index))
                        for index, parameter in enumerate(self.parameters)]

    def path(self, index, suffix):
        return self.directory / f"{index:06d}.{suffix}"

    def capture(self, parameter, index):
        import torch
        self.check()
        if parameter.grad is None:
            return
        if parameter.grad.is_sparse:
            raise ValueError("Disk AdamW requires dense gradients.")
        gradient = parameter.grad.detach().contiguous().view(-1)
        accumulate = index in self.indices
        with self.path(index,'grad').open('r+b' if accumulate else 'wb') as stream:
            for offset in range(0, gradient.numel(), self.chunk_elements):
                self.check()
                chunk = gradient[offset:offset+self.chunk_elements].to(device='cpu',dtype=torch.float32)
                if accumulate:
                    position = stream.tell()
                    old = torch.frombuffer(bytearray(stream.read(chunk.numel()*4)),dtype=torch.float32)
                    chunk = old.add_(chunk)
                    stream.seek(position)
                stream.write(chunk.numpy().tobytes())
        self.indices.add(index)
        parameter.grad = None

    def zero_grad(self, set_to_none=True):
        for parameter in self.parameters:
            parameter.grad = None
        self.indices.clear()
        self.coefficient = 1.0

    def clip_grad_norm(self, maximum=1.0):
        import torch
        squared = 0.0
        for index in self.indices:
            with self.path(index,'grad').open('rb') as stream:
                while block := stream.read(BUFFER_BYTES):
                    self.check()
                    chunk = torch.frombuffer(bytearray(block),dtype=torch.float32)
                    squared += chunk.double().square().sum().item()
        norm = math.sqrt(squared)
        if not math.isfinite(norm):
            raise ValueError("Training gradients became non-finite.")
        self.coefficient = min(1.0, maximum/(norm+1e-6))
        return torch.tensor(norm)

    def step(self):
        import torch
        beta1, beta2 = self.betas
        with torch.no_grad():
            for index in sorted(self.indices):
                self.check()
                parameter = self.parameters[index]
                if not parameter.is_contiguous():
                    raise ValueError("Disk AdamW requires contiguous trainable parameters.")
                flat = parameter.view(-1)
                count = self.steps.get(index,0)+1
                step_size = self.lr/(1-beta1**count)
                correction = math.sqrt(1-beta2**count)
                old = index in self.steps
                with self.path(index,'grad').open('rb') as gradients, self.path(index,'m').open('r+b' if old else 'w+b') as first, self.path(index,'v').open('r+b' if old else 'w+b') as second:
                    for offset in range(0,flat.numel(),self.chunk_elements):
                        self.check()
                        length = min(self.chunk_elements,flat.numel()-offset)
                        gradient = torch.frombuffer(bytearray(gradients.read(length*4)),dtype=torch.float32).mul_(self.coefficient)
                        position = first.tell()
                        m = torch.frombuffer(bytearray(first.read(length*4)),dtype=torch.float32) if old else torch.zeros(length)
                        v = torch.frombuffer(bytearray(second.read(length*4)),dtype=torch.float32) if old else torch.zeros(length)
                        m.lerp_(gradient,1-beta1)
                        v.mul_(beta2).addcmul_(gradient,gradient,value=1-beta2)
                        denominator = v.sqrt().div_(correction).add_(self.eps)
                        weights = flat[offset:offset+length].detach().to(device='cpu',dtype=torch.float32)
                        weights.mul_(1-self.lr*self.weight_decay).addcdiv_(m,denominator,value=-step_size)
                        if parameter.device.type != 'cpu' or parameter.dtype != torch.float32:
                            flat[offset:offset+length].copy_(weights)
                        first.seek(position); second.seek(position)
                        first.write(m.numpy().tobytes()); second.write(v.numpy().tobytes())
                self.steps[index] = count
        (self.directory/'steps.json').write_text(json.dumps(self.steps),encoding='utf-8')

    def close(self):
        for handle in self.handles:
            handle.remove()
        self.handles.clear()

    def state_dict(self):
        raise RuntimeError("Disk-backed optimizer working state is not embedded in a model checkpoint. Continuation reloads verified weights with fresh optimizer state.")

    def load_state_dict(self, state):
        raise RuntimeError("Disk-backed AdamW starts fresh optimizer state when continuing a verified model checkpoint.")
