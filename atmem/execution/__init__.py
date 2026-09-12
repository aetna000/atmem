"""Durable, content-minimizing execution evidence."""

from .events import CoverageGap, DeliveryDecision, ProducerEvent
from .projection import execution_projection

__all__ = ["CoverageGap", "DeliveryDecision", "ProducerEvent", "execution_projection"]
