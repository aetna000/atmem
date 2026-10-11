"""Synthetic formation dataset compiler for Spec 041."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .generator import build_scenario, generate_scenarios
    from .models import FormationScenarioV1, TypedDecisionExampleV1

__all__ = ["FormationScenarioV1", "TypedDecisionExampleV1", "build_scenario", "generate_scenarios"]


def __getattr__(name: str) -> Any:
    """Keep dataset construction optional for lightweight publication/training tools."""
    if name in {"build_scenario", "generate_scenarios"}:
        from . import generator

        return getattr(generator, name)
    if name in {"FormationScenarioV1", "TypedDecisionExampleV1"}:
        from . import models

        return getattr(models, name)
    raise AttributeError(name)
