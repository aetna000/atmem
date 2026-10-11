"""Optional typed-decision support for governed AtMem formation."""

from .packing import (
    AuthorizedRange,
    PackedDecisionInput,
    PackingAdapter,
    pack_authorized_ranges,
)
from .contracts import (
    CalibrationBinding,
    DecisionReceiptV1,
    FormationDecisionRequest,
    FormationDecisionResponse,
    QuestionDefinitionV1,
)
from .runtime import LayaDecisionEngine, select_device
from .escalation import AtBotFormationEscalator, EscalationPolicy, EscalationResult

__all__ = [
    "AuthorizedRange",
    "PackedDecisionInput",
    "PackingAdapter",
    "pack_authorized_ranges",
    "CalibrationBinding",
    "DecisionReceiptV1",
    "FormationDecisionRequest",
    "FormationDecisionResponse",
    "QuestionDefinitionV1",
    "LayaDecisionEngine",
    "select_device",
    "AtBotFormationEscalator",
    "EscalationPolicy",
    "EscalationResult",
]
