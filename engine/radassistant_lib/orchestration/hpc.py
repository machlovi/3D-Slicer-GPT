"""HPC offload — decide by a COST TABLE (not LLM guesswork) and submit via a TEMPLATED,
allow-listed SLURM script. The model never emits raw sbatch/shell.

Research + the project's own guiding principle: heavy jobs (TotalSegmentator ~40 min CPU
vs ~40 s GPU, radiomics, nnInteractive) should run on the HPC when there's no capable local
GPU and the cluster is reachable. The trigger is a lookup table; the submission is a
parameterized template whose inputs are validated against allow-lists, so an injected
partition/account/command can't turn into arbitrary remote execution. Every submission is
routed through the human approval gate by the caller.

Pure logic + string generation (no subprocess here), unit-tested (tests/test_infra.py).
"""

import re

# tool -> (needs_gpu, approx_gpu_seconds, approx_cpu_seconds, min_vram_gb)
TOOL_COST = {
    "run_total_segmentator": (True, 45, 2700, 7),
    "ts_run_total_segmentator": (True, 45, 2700, 7),
    "extract_radiomics": (False, 20, 120, 0),
    "nn_interactive": (True, 5, 600, 6),
    "medgemma_infer": (True, 8, 900, 16),
}

_PARTITION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
_ACCOUNT_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
_JOBNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,48}$")
_MODULE_RE = re.compile(r"^[a-zA-Z0-9_./-]{1,64}$")   # module names have slashes: gcc11/11.3.0


def should_offload(tool_name, *, local_gpu=False, cluster_reachable=False):
    """Return (offload: bool, reason)."""
    cost = TOOL_COST.get(tool_name)
    if cost is None:
        return False, "not a heavy tool"
    needs_gpu, gpu_s, cpu_s, _vram = cost
    if not needs_gpu:
        return False, "runs fine locally on CPU"
    if local_gpu:
        return False, "a local GPU is available"
    if not cluster_reachable:
        return False, "no local GPU and cluster is unreachable — will run locally (slow)"
    speedup = max(1, cpu_s // max(1, gpu_s))
    return True, f"GPU tool with no local GPU; HPC ~{speedup}x faster — offload"


class SlurmJob:
    """A validated SLURM submission request. Raises ValueError on bad input."""

    def __init__(self, *, job_name, partition, account, command, time="01:00:00",
                 gpus=1, cpus=8, mem_gb=32, modules=None):
        if not _JOBNAME_RE.match(job_name or ""):
            raise ValueError("invalid job_name")
        if not _PARTITION_RE.match(partition or ""):
            raise ValueError("invalid partition")
        if not _ACCOUNT_RE.match(account or ""):
            raise ValueError("invalid account")
        if not re.match(r"^\d{1,2}:\d{2}:\d{2}$", time or ""):
            raise ValueError("invalid time (want HH:MM:SS)")
        for n, v in (("gpus", gpus), ("cpus", cpus), ("mem_gb", mem_gb)):
            if not isinstance(v, int) or not (0 <= v <= 512):
                raise ValueError(f"invalid {n}")
        # command must come from our allow-list of templates, not free-form shell
        if command not in ALLOWED_COMMANDS:
            raise ValueError("command is not an allow-listed job template")
        self.job_name = job_name
        self.partition = partition
        self.account = account
        self.command = command
        self.time = time
        self.gpus = gpus
        self.cpus = cpus
        self.mem_gb = mem_gb
        self.modules = list(modules or [])

    def render(self):
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={self.job_name}",
            f"#SBATCH --partition={self.partition}",
            f"#SBATCH --account={self.account}",
            f"#SBATCH --time={self.time}",
            f"#SBATCH --gres=gpu:{self.gpus}" if self.gpus else "",
            f"#SBATCH --cpus-per-task={self.cpus}",
            f"#SBATCH --mem={self.mem_gb}G",
            f"#SBATCH --output={self.job_name}-%j.log",
            "set -euo pipefail",
        ]
        lines += [f"module load {m}" for m in self.modules if _MODULE_RE.match(m)]
        lines.append(ALLOWED_COMMANDS[self.command])
        return "\n".join(l for l in lines if l)


# allow-listed job bodies — the only commands a generated script may contain
ALLOWED_COMMANDS = {
    "totalsegmentator": ('TotalSegmentator -i "$INPUT" -o "$OUTPUT" --fast'),
    "serve_ollama": ('OLLAMA_HOST=0.0.0.0:11434 ollama serve'),
    "serve_llamacpp_vision": (
        'llama-server -m "$MODEL" --mmproj "$MMPROJ" --host 127.0.0.1 --port 11437 --jinja'),
}
