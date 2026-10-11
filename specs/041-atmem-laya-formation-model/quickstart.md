# Planned User Journey

This is acceptance-oriented documentation; command names must be reconciled
with the existing CLI before implementation.

1. Install or upgrade AtMem normally. No Laya dependency or weights are fetched.
2. Run the guided Laya setup command (or its documented noninteractive form).
   It resolves a pinned model, checks license/digest/device and shows a preview.
3. Inspect `doctor`/status for exact revision, question schema, calibration,
   device and deterministic fallback.
4. Explicitly activate the Laya formation profile. Generative escalation remains
   separately configurable and can be disabled.
5. Inspect decision receipts and review cases. Roll back to the previous profile
   without migrating or deleting canonical memory.

Expected failure behavior: offline install, missing accelerator, corrupt weights,
provider denial or model timeout leaves the deterministic profile usable and
prints an actionable diagnostic. No partial activation is allowed.
