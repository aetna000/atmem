"""Versioned local Python-host identity, not a claim about remote tool runtimes."""
from importlib.metadata import distributions
import platform
import sys

from atmem.knowledge.contracts import stable_digest


def environment_digest():
    packages = sorted({(str(d.metadata.get("Name", "")).casefold(), str(d.version)) for d in distributions()})
    return stable_digest({"format": "atmem-code-python-host-environment-v1",
                          "implementation": sys.implementation.name, "python": platform.python_version(),
                          "system": platform.system(), "machine": platform.machine(), "packages": packages})
