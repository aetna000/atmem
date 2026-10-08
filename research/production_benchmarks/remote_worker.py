"""Fail-closed identity checks for paid remote benchmark workers."""

from __future__ import annotations

import os
import platform
import subprocess
from typing import Any, Callable


REMOTE_HARDWARE_PROFILE = (
    "RunPod-SECURE;Linux;x86_64;NVIDIA-A100-SXM4-80GB;remote-worker-v1"
)


def require_remote_paid_worker(
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Prove paid benchmark work is on the pinned RunPod worker.

    Environment labels are necessary to bind the orchestrator-selected pod,
    while the operating system, architecture and GPU are verified from the
    worker itself.  This function is intentionally called before dataset or
    checkpoint hashing so an operator workstation cannot accidentally start
    benchmark work.
    """

    if platform.system() != "Linux" or platform.machine() not in {
        "x86_64", "AMD64"
    }:
        raise RuntimeError(
            "paid benchmark workers must run on the pinned RunPod Linux host; "
            "the operator workstation is orchestration-only"
        )
    if os.environ.get("ATMEM_BENCHMARK_EXECUTION_SITE", "").strip() != "runpod":
        raise RuntimeError("remote worker lacks ATMEM_BENCHMARK_EXECUTION_SITE=runpod")
    pod_id = os.environ.get("RUNPOD_POD_ID", "").strip()
    if not pod_id:
        raise RuntimeError("remote worker lacks the RunPod pod identity")
    if os.environ.get("ATMEM_RUNPOD_CLOUD_TYPE", "").strip() != "SECURE":
        raise RuntimeError("paid benchmark worker is not bound to RunPod SECURE cloud")

    completed = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    rows = [row.strip() for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise RuntimeError("paid benchmark worker must expose exactly one pinned GPU")
    try:
        gpu_name, memory_text = [part.strip() for part in rows[0].rsplit(",", 1)]
        memory_mib = int(memory_text)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("could not parse remote GPU identity") from exc
    normalized = gpu_name.upper().replace(" ", "-").replace("_", "-")
    if "A100-SXM4-80GB" not in normalized or memory_mib < 80_000:
        raise RuntimeError(
            f"remote GPU differs from pinned A100-SXM4-80GB: {gpu_name}, "
            f"{memory_mib} MiB"
        )
    return {
        "hardware_profile": REMOTE_HARDWARE_PROFILE,
        "execution_site": "runpod",
        "cloud_type": "SECURE",
        "pod_id": pod_id,
        "os": "Linux",
        "architecture": "x86_64",
        "gpu_name": gpu_name,
        "gpu_memory_mib": memory_mib,
    }
