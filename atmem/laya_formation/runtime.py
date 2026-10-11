"""Bounded, calibrated runtime for the optional AtMem Laya profile."""

from __future__ import annotations

import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from .artifacts import ArtifactBundle, dependency_status
from .contracts import FormationDecisionRequest, FormationDecisionResponse
from .packing import LayaPackingAdapter, PackingAdapter


_DEVICES = {"auto", "cpu", "cuda", "mps"}


def select_device(requested: str = "auto", *, torch_module: Any | None = None) -> str:
    """Resolve a declared device without silently changing an explicit request."""

    value = str(requested).strip().lower()
    if value not in _DEVICES and not value.startswith("cuda:"):
        raise ValueError("device must be auto, cpu, mps, cuda or cuda:<index>")
    if value == "cpu":
        return "cpu"
    if torch_module is None:
        try:
            import torch as torch_module
        except ImportError:
            if value == "auto":
                return "cpu"
            raise RuntimeError("the requested accelerator requires the optional PyTorch runtime") from None
    cuda_available = bool(torch_module.cuda.is_available())
    mps_backend = getattr(getattr(torch_module, "backends", None), "mps", None)
    mps_available = bool(mps_backend is not None and mps_backend.is_available())
    if value == "auto":
        return "cuda" if cuda_available else "mps" if mps_available else "cpu"
    if value.startswith("cuda"):
        if not cuda_available:
            raise RuntimeError("CUDA was explicitly requested but is unavailable")
        if ":" in value:
            try:
                index = int(value.split(":", 1)[1])
            except ValueError:
                raise ValueError("CUDA device index must be an integer") from None
            if index < 0 or index >= int(torch_module.cuda.device_count()):
                raise RuntimeError("the requested CUDA device index is unavailable")
        return value
    if not mps_available:
        raise RuntimeError("MPS was explicitly requested but is unavailable")
    return "mps"


def _bucket(option_count: int) -> str:
    size = "2" if option_count <= 2 else "3-5" if option_count <= 5 else "6-10" if option_count <= 10 else "11+"
    return f"choice:{size}"


class LayaDecisionEngine:
    """Evaluate one verified finite-choice request and return only a proposal.

    Artifact download and profile activation are deliberately outside this class.  A
    caller supplies an already verified bundle. Optional test doubles are accepted so
    contract tests do not import or download the Laya stack.
    """

    def __init__(
        self,
        bundle: ArtifactBundle,
        *,
        device: str = "auto",
        max_inference_ms: float = 30_000.0,
        agent: Any | None = None,
        packing_adapter: PackingAdapter | None = None,
    ) -> None:
        if not math.isfinite(float(max_inference_ms)) or float(max_inference_ms) <= 0:
            raise ValueError("max_inference_ms must be finite and positive")
        bundle.calibration.validate()
        self.bundle = bundle
        self.device = select_device(device)
        self.max_inference_ms = float(max_inference_ms)
        self._last_diagnostics: dict[str, Any] = {
            "state": "not_run", "device": self.device,
            "model_revision": bundle.revision,
        }

        if agent is None:
            status = dependency_status()
            if not status["available"]:
                raise RuntimeError("install atmem[laya-formation] before activating the Laya profile")
            if status["versions"].get("laya") != "0.4.2":
                raise RuntimeError("Laya runtime version mismatch")
            from laya import Agent

            inventory = json.loads((bundle.root / "artifact-manifest.json").read_text(encoding="utf-8"))["inventory"]
            expected = {item["path"]: item["sha256"] for item in inventory}
            agent = Agent(
                str(bundle.root), device=self.device, expected_sha256=expected,
            )
            # AtMem's checksum-bound bundle carries additional lineage and uses a
            # deliberately different public schema from Laya's standalone calibration
            # file. Install only the already-validated temperature fields in memory.
            from laya.calibrate import apply_calibration_payload
            apply_calibration_payload(agent, {
                "version": 1,
                "temperature": list(bundle.calibration.temperatures),
                "temperature_by_options": dict(bundle.calibration.temperature_by_options),
                "binning_map": None,
            })
            self._verify_agent_calibration(agent)
        self.agent = agent
        self.packing_adapter = packing_adapter or LayaPackingAdapter(
            agent.tok, revision=self._tokenizer_revision(bundle.root),
        )

    @staticmethod
    def _tokenizer_revision(root: Path) -> str:
        manifest = json.loads((root / "training-manifest.json").read_text(encoding="utf-8"))
        base_model = manifest.get("base_model", {})
        value = base_model.get("revision") if isinstance(base_model, Mapping) else None
        if isinstance(value, str) and value:
            return value
        for key in ("tokenizer_revision", "laya_revision"):
            value = manifest.get(key)
            if isinstance(value, str) and value:
                return value
        lineage = manifest.get("lineage", {})
        value = lineage.get("laya_revision") or lineage.get("source_revision")
        if not isinstance(value, str) or not value:
            raise ValueError("artifact does not bind a tokenizer revision")
        return value

    def _verify_agent_calibration(self, agent: Any) -> None:
        expected = self.bundle.calibration
        actual_type = tuple(float(value) for value in agent.temperature_raw)
        actual_buckets = {str(key): float(value) for key, value in agent.temperature_by_options_raw.items()}
        if actual_type != tuple(expected.temperatures) or actual_buckets != {
            str(key): float(value) for key, value in expected.temperature_by_options.items()
        }:
            raise ValueError("loaded Laya calibration differs from the verified artifact binding")

    def _verify_binding(self, request: FormationDecisionRequest) -> None:
        request.assert_model_ready()
        if request.calibration.to_dict() != self.bundle.calibration.to_dict():
            raise ValueError("request calibration differs from the verified artifact binding")
        frozen = self.bundle.questions.get(request.question.question_id)
        if not isinstance(frozen, Mapping):
            raise ValueError("question is not supported by the verified model artifact")
        if frozen.get("instructions") != request.question.instructions or tuple(frozen.get("choice_ids", ())) != request.question.choice_ids:
            raise ValueError("question definition differs from the verified model artifact")
        if request.question.tokenizer_revision != self.packing_adapter.revision:
            raise ValueError("question tokenizer revision differs from the active exact packer")

        try:
            parsed = json.loads(request.packed_input.state)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("packed state is not canonical JSON") from None
        serialized, token_ids = self.packing_adapter.serialize_and_encode_state(parsed)
        if serialized != request.packed_input.state or len(token_ids) != request.packed_input.state_tokens:
            raise ValueError("packed state differs from tokenizer-exact runtime encoding")

    def __call__(self, request: FormationDecisionRequest) -> FormationDecisionResponse:
        self._verify_binding(request)
        started = perf_counter()
        try:
            raw = self.agent.system_one(
                request.packed_input.state,
                {request.question.question_id: request.question.to_laya()},
                max_len=request.question.max_len,
                head_max_len=request.question.head_max_len,
            )
            elapsed_ms = (perf_counter() - started) * 1_000.0
            if elapsed_ms > self.max_inference_ms:
                raise TimeoutError("bounded Laya inference exceeded its configured deadline")
            usage = raw.get("usage")
            if not isinstance(usage, Mapping):
                raise ValueError("model response has no bounded usage record")
            if usage.get("truncated") or int(usage.get("state_tokens_dropped", 0)) != 0:
                raise ValueError("model runtime truncated a tokenizer-exact request")
            answer = raw.get("answers", {}).get(request.question.question_id)
            if not isinstance(answer, Mapping) or answer.get("type") != "choice":
                raise ValueError("model response is not the requested finite choice")
            scores = {str(key): float(value) for key, value in dict(answer.get("probabilities", {})).items()}
            known = set(request.question.choice_ids)
            if set(scores) != known:
                raise ValueError("model score vector differs from the finite choice set")
            if any(not math.isfinite(value) or value < 0 or value > 1 for value in scores.values()):
                raise ValueError("model score vector contains an invalid probability")
            if abs(sum(scores.values()) - 1.0) > 0.001:
                raise ValueError("model probability vector does not sum to one")
            confidence = float(answer.get("answer_confidence"))
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("model confidence is invalid")
            maximum = max(scores.values())
            winners = [choice for choice, value in scores.items() if value == maximum]
            if len(winners) != 1 or answer.get("choice") != winners[0]:
                raise ValueError("model choice is inconsistent with its score vector")
            if abs(confidence - maximum) > 0.00011:
                raise ValueError("calibrated confidence differs from the winning probability")

            bucket = _bucket(len(scores))
            threshold = self.bundle.calibration.thresholds.get(bucket)
            if threshold is None:
                raise ValueError("no calibrated abstention threshold exists for this option bucket")
            abstained = round(confidence, 4) < float(threshold)
            response = FormationDecisionResponse(
                request_id=request.request_id,
                selected_choice_ids=() if abstained else (winners[0],),
                calibrated_scores=scores,
                confidence=round(confidence, 4),
                abstained=abstained,
                reason_code="calibrated_low_confidence" if abstained else "laya_calibrated_choice",
            )
            response.validate(request.question)
            self._last_diagnostics = {
                "state": "abstained" if abstained else "proposed",
                "request_id": request.request_id,
                "input_digest": request.packed_input.state_digest,
                "model_revision": self.bundle.revision,
                "questions_digest": self.bundle.questions_digest,
                "calibration_digest": self.bundle.calibration_digest,
                "device": self.device,
                "latency_ms": elapsed_ms,
                "input_tokens": int(usage.get("input_tokens", 0)),
                "reason_code": response.reason_code,
            }
            return response
        except Exception as exc:
            self._last_diagnostics = {
                "state": "rejected", "request_id": request.request_id,
                "input_digest": request.packed_input.state_digest,
                "model_revision": self.bundle.revision, "device": self.device,
                "reason_code": type(exc).__name__,
            }
            raise

    def diagnostics(self) -> dict[str, Any]:
        """Return identifiers and measurements only; never source or packed content."""

        return dict(self._last_diagnostics)

    def close(self) -> None:
        exit_method = getattr(self.agent, "__exit__", None)
        if callable(exit_method):
            exit_method(None, None, None)
