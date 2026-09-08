"""Fail-closed production configuration validation."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ProductionConfig:
    public_bind: bool = False
    tls_cert: str | None = None
    tls_key: str | None = None
    secret_reference: str | None = None
    encryption_key_reference: str | None = None
    retention_days: int = 30
    tenant_quota: int = 100_000
    worker_lease_seconds: int = 60
    def validate(self) -> None:
        if self.public_bind and not (self.tls_cert and self.tls_key): raise ValueError("public bind requires TLS certificate and key")
        if self.public_bind and not self.secret_reference: raise ValueError("public bind requires an external secret reference")
        if not self.encryption_key_reference: raise ValueError("production storage requires an encryption key reference")
        if self.retention_days <= 0 or self.tenant_quota <= 0 or self.worker_lease_seconds <= 0: raise ValueError("retention, quota, and lease values must be positive")
