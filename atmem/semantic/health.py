"""Authoritative, UI-neutral semantic index health contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from importlib.resources import files
import json
import os
import platform
import shutil
from typing import Any, Mapping, Sequence

from atmem.core.canonical import canonical_json, sha256_hex


HEALTH_FORMAT = "atmem-semantic-health-v1"
MANIFEST_FORMAT = "atmem-semantic-manifest-v1"
CATALOG_FORMAT = "atmem-semantic-model-catalog-v1"


class SemanticHealthStatus(str, Enum):
    """Stable health vocabulary shared by CLI and dashboard clients."""

    MISSING = "missing"
    LEGACY = "legacy"
    WEAK = "weak"
    STALE = "stale"
    INCOMPATIBLE = "incompatible"
    REBUILDING = "rebuilding"
    HEALTHY = "healthy"


class SemanticHealthReason(str, Enum):
    NO_ACTIVE_EPOCH = "no_active_epoch"
    BUILD_IN_PROGRESS = "build_in_progress"
    MANIFEST_INCOMPLETE = "manifest_incomplete"
    HASHING_FALLBACK = "hashing_fallback"
    IDENTITY_MISMATCH = "identity_mismatch"
    DIMENSION_MISMATCH = "dimension_mismatch"
    INDEX_DIRTY = "index_dirty"
    CANONICAL_DRIFT = "canonical_drift"
    POLICY_CHANGED = "policy_changed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class SemanticManifest:
    epoch_id: str
    subject_id: str
    provider: str
    model: str
    revision: str
    dimensions: int
    normalization: str
    configuration_sha256: str
    source_sha256: str
    canonical_generation: int
    record_count: int
    created_at: str
    status: str
    format: str = MANIFEST_FORMAT

    def __post_init__(self) -> None:
        if not self.epoch_id or not self.subject_id:
            raise ValueError("manifest epoch_id and subject_id are required")
        if self.dimensions < 1:
            raise ValueError("manifest dimensions must be positive")
        if self.record_count < 0 or self.canonical_generation < 0:
            raise ValueError("manifest counters cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SemanticHealth:
    status: SemanticHealthStatus
    subject_id: str
    reasons: tuple[SemanticHealthReason, ...]
    actions: tuple[str, ...]
    manifest: SemanticManifest | None = None
    verification_sha256: str | None = None
    format: str = HEALTH_FORMAT

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "status": self.status.value,
            "subject_id": self.subject_id,
            "reasons": [reason.value for reason in self.reasons],
            "actions": list(self.actions),
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "verification_sha256": self.verification_sha256,
        }


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Observed hardware. `memory_gib` is ``None`` when it could not be measured.

    Unmeasured memory is reported as unknown rather than zero so a platform
    without ``sysconf`` is never described as having no memory.
    """

    memory_gib: float | None
    architecture: str
    accelerator: str = "none"
    cpu_count: int = 1

    @property
    def memory_known(self) -> bool:
        return self.memory_gib is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_gib": self.memory_gib,
            "memory_known": self.memory_known,
            "architecture": self.architecture,
            "accelerator": self.accelerator,
            "cpu_count": self.cpu_count,
        }

    @classmethod
    def detect(cls) -> "HardwareProfile":
        memory_gib: float | None = None
        try:
            memory_gib = (
                float(os.sysconf("SC_PHYS_PAGES"))
                * float(os.sysconf("SC_PAGE_SIZE"))
                / 1024**3
            )
        except (ValueError, OSError, AttributeError):
            memory_gib = None
        return cls(
            memory_gib=memory_gib,
            architecture=platform.machine().lower() or "unknown",
            accelerator=detect_accelerator(),
            cpu_count=os.cpu_count() or 1,
        )


def detect_accelerator() -> str:
    """Report an observed accelerator without importing an optional runtime.

    Only evidence available from the platform and PATH is used, so the answer
    is never stronger than what was actually observed.
    """

    if platform.system() == "Darwin" and platform.machine().lower() in {
        "arm64",
        "aarch64",
    }:
        return "metal"
    if shutil.which("nvidia-smi"):
        return "cuda"
    if shutil.which("rocminfo"):
        return "rocm"
    return "none"


def load_model_catalog() -> dict[str, Any]:
    resource = files("atmem.semantic").joinpath("models.json")
    catalog = json.loads(resource.read_text(encoding="utf-8"))
    if catalog.get("format") != CATALOG_FORMAT:
        raise ValueError("unsupported semantic model catalog format")
    return catalog


def recommend_local_models(
    hardware: HardwareProfile, catalog: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return compatible models in stable preference order.

    When memory could not be measured the memory filter is not applied and
    every returned entry is marked `memory_unverified`, so an unmeasurable
    platform gets a caveated list instead of an empty one.
    """

    source = catalog or load_model_catalog()
    compatible = []
    for model in source.get("models", []):
        architectures = model.get("architectures", ["any"])
        if (
            hardware.memory_known
            and float(hardware.memory_gib or 0.0) < float(model["minimum_memory_gib"])
        ):
            continue
        if "any" not in architectures and hardware.architecture not in architectures:
            continue
        entry = dict(model)
        entry["memory_unverified"] = not hardware.memory_known
        compatible.append(entry)
    return sorted(
        compatible,
        key=lambda item: (int(item["priority"]), str(item["provider"]), str(item["model"])),
    )


def evaluate_semantic_health(
    subject_id: str,
    *,
    active_epoch: Mapping[str, Any] | None,
    epochs: Sequence[Mapping[str, Any]] = (),
    verification: Mapping[str, Any] | None = None,
    expected_identity: Mapping[str, Any] | None = None,
    source_sha256: str | None = None,
    canonical_generation: int = 0,
    policy_sha256: str | None = None,
) -> SemanticHealth:
    """Evaluate health from persisted evidence without performing mutations."""

    building = any(epoch.get("status") == "building" for epoch in epochs)
    if active_epoch is None:
        status = SemanticHealthStatus.REBUILDING if building else SemanticHealthStatus.MISSING
        reason = (
            SemanticHealthReason.BUILD_IN_PROGRESS
            if building
            else SemanticHealthReason.NO_ACTIVE_EPOCH
        )
        return SemanticHealth(status, subject_id, (reason,), ("rebuild",))

    if int(active_epoch.get("dimensions", 0)) < 1:
        return SemanticHealth(
            SemanticHealthStatus.INCOMPATIBLE,
            subject_id,
            (SemanticHealthReason.DIMENSION_MISMATCH,),
            ("verify", "rebuild"),
            verification_sha256=_report_digest(verification),
        )
    manifest = _manifest(active_epoch, subject_id, source_sha256, canonical_generation)
    if building:
        return SemanticHealth(
            SemanticHealthStatus.REBUILDING,
            subject_id,
            (SemanticHealthReason.BUILD_IN_PROGRESS,),
            ("verify", "resume_rebuild", "discard_partial"),
            manifest,
            _report_digest(verification),
        )
    if manifest is None:
        return SemanticHealth(
            SemanticHealthStatus.LEGACY,
            subject_id,
            (SemanticHealthReason.MANIFEST_INCOMPLETE,),
            ("rebuild",),
            verification_sha256=_report_digest(verification),
        )
    if expected_identity and not _identity_matches(active_epoch, expected_identity):
        return _unhealthy(
            SemanticHealthStatus.INCOMPATIBLE,
            SemanticHealthReason.IDENTITY_MISMATCH,
            subject_id,
            manifest,
            verification,
        )
    if bool(active_epoch.get("dirty")):
        return _unhealthy(
            SemanticHealthStatus.STALE,
            SemanticHealthReason.INDEX_DIRTY,
            subject_id,
            manifest,
            verification,
        )
    # A recorded policy digest that no longer matches means the derived vectors
    # were produced under a different household policy. Epochs built before the
    # digest existed record nothing and are left alone rather than falsely aged.
    epoch_policy = _epoch_policy_sha256(active_epoch)
    if policy_sha256 and epoch_policy and epoch_policy != policy_sha256:
        return _unhealthy(
            SemanticHealthStatus.STALE,
            SemanticHealthReason.POLICY_CHANGED,
            subject_id,
            manifest,
            verification,
        )
    if verification is not None and not bool(verification.get("valid")):
        reason = (
            SemanticHealthReason.CANONICAL_DRIFT
            if any(
                verification.get(name)
                for name in ("stale_vectors", "coverage_gaps", "tombstoned_vectors")
            )
            else SemanticHealthReason.VERIFICATION_FAILED
        )
        return _unhealthy(
            SemanticHealthStatus.STALE,
            reason,
            subject_id,
            manifest,
            verification,
        )
    provider = str(active_epoch.get("provider", "")).lower()
    if provider in {"hashing", "hashing-diagnostic", "hash", "deterministic-hashing"}:
        return SemanticHealth(
            SemanticHealthStatus.WEAK,
            subject_id,
            (SemanticHealthReason.HASHING_FALLBACK,),
            ("setup", "rebuild"),
            manifest,
            _report_digest(verification),
        )
    return SemanticHealth(
        SemanticHealthStatus.HEALTHY,
        subject_id,
        (SemanticHealthReason.VERIFIED,),
        ("verify", "rebuild"),
        manifest,
        _report_digest(verification),
    )


def inspect_semantic_health(
    index: Any,
    memory: Any,
    subject_id: str,
    *,
    expected_identity: Mapping[str, Any] | None = None,
) -> SemanticHealth:
    """Build the canonical evidence bundle and evaluate an index."""

    status = index.status(subject_id)
    active = index.active_epoch(subject_id)
    verification = index.verify(memory, subject_id) if active else None
    records = memory.store.list_records(subject_id)
    snapshot = [
        {"id": row["id"], "status": row["status"], "content": row["content"]}
        for row in records
    ]
    source_sha256 = f"sha256:{sha256_hex(canonical_json(snapshot))}"
    return evaluate_semantic_health(
        subject_id,
        active_epoch=active,
        epochs=status["epochs"],
        verification=verification,
        expected_identity=expected_identity,
        source_sha256=source_sha256,
        canonical_generation=memory.store.record_generation(subject_id),
        policy_sha256=index.policy_fingerprint(),
    )


def _manifest(
    epoch: Mapping[str, Any],
    subject_id: str,
    source_sha256: str | None,
    canonical_generation: int,
) -> SemanticManifest | None:
    identity = epoch.get("identity")
    required = ("epoch_id", "provider", "model", "model_version", "dimensions", "created_at")
    if not isinstance(identity, Mapping) or not all(epoch.get(key) is not None for key in required):
        return None
    normalization = identity.get("normalization")
    identity_sha256 = epoch.get("identity_sha256")
    if not normalization or not identity_sha256 or not source_sha256:
        return None
    return SemanticManifest(
        epoch_id=str(epoch["epoch_id"]),
        subject_id=subject_id,
        provider=str(epoch["provider"]),
        model=str(epoch["model"]),
        revision=str(epoch["model_version"]),
        dimensions=int(epoch["dimensions"]),
        normalization=str(normalization),
        configuration_sha256=str(identity_sha256),
        source_sha256=source_sha256,
        canonical_generation=int(canonical_generation),
        record_count=int(epoch.get("entry_count", 0)),
        created_at=str(epoch["created_at"]),
        status=str(epoch.get("status", "unknown")),
    )


def _epoch_policy_sha256(epoch: Mapping[str, Any]) -> str | None:
    identity = epoch.get("identity")
    if not isinstance(identity, Mapping):
        return None
    value = identity.get("policy_sha256")
    return str(value) if value else None


def _identity_matches(epoch: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
    identity = epoch.get("identity", {})
    keys = ("provider", "model", "version", "model_digest", "endpoint", "normalization")
    return all(
        key not in expected or str(expected.get(key)) == str(identity.get(key))
        for key in keys
    )


def _report_digest(report: Mapping[str, Any] | None) -> str | None:
    return str(report["report_sha256"]) if report and report.get("report_sha256") else None


def _unhealthy(
    status: SemanticHealthStatus,
    reason: SemanticHealthReason,
    subject_id: str,
    manifest: SemanticManifest,
    verification: Mapping[str, Any] | None,
) -> SemanticHealth:
    return SemanticHealth(
        status,
        subject_id,
        (reason,),
        ("verify", "rebuild"),
        manifest,
        _report_digest(verification),
    )
