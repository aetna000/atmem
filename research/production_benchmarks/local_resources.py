"""Resource guardrails for benchmark orchestration on the operator Mac."""

from __future__ import annotations

import os
import platform
from typing import Any


THREAD_LIMIT_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def configure_local_resource_limits(*, niceness_increment: int = 10) -> dict[str, Any]:
    """Bound local CPU parallelism and lower orchestration priority.

    The paid reader remains remote. These settings apply to the controller and
    every local child process so formation/retrieval cannot saturate the Mac.
    """

    if platform.system() != "Darwin":
        raise RuntimeError("the benchmark controller must run on the pinned Mac")
    for name in THREAD_LIMIT_ENV:
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    applied_niceness = os.nice(niceness_increment)
    return {
        "case_concurrency": 1,
        "thread_limit": 1,
        "niceness": applied_niceness,
        "tokenizers_parallelism": False,
    }
