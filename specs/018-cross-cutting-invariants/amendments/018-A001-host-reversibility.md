# 018-A001: Host-neutral reversibility

**Date**: 2026-09-09
**Authority**: Spec 018 FR-008; explicitly requested product correction.
**Invariant**: INV-009 (unchanged)
**Principles**: III — Safe Defaults and Reversibility; V — Contract-First Host Neutrality; VI — Executable Claims.

Previous guarantee: “OpenClaw migration remains reversible.”

Amended guarantee: “Host integration remains reversible.”

The guarantee applies to AtMem's integration changes: preserve host-owned state, disable introduced hooks/context influence and provide a verified recovery path after interrupted activation. It does not promise to undo external agent actions or retract delivered context.

OpenClaw is the initial baseline configuration, retaining `delivery.openclaw_restore`. Each additional host needs version/configuration-specific activation, disable, restore and interrupted-recovery assertions through Spec 011. Unsupported or untested restoration remains explicit; renaming the invariant adds no evidence and confers no new verified-host status.

Compatibility: keep INV-009, its assertion ID, the registry-v1 wire shape and historical reports. Advance registry content version from 1.0.0 to 1.1.0; consumers compare stable IDs rather than display text. Legacy `base` assertion results retain their historical meaning and do not establish cross-host coverage. No persisted memory migration or package release is part of this amendment.

Replacement coverage: preserve existing OpenClaw restore tests and require additional host assertions through the public conformance kit. The current offline invariant gate aggregates suite results and the baseline registry-presence test alone is not a live restore test; host guarantees require actual host evidence. Spec 018 T015–T017 still own stronger per-assertion/configuration reporting.

Verification for the amendment: registry tests check serialized amendment metadata, stable identity/assertion, and uncovered declared host configurations. Broader host delivery remains planned work in Spec 011.
