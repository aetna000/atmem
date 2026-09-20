# Releases and upgrades

## Stable release
[AtMem 2.3.4](../releases/v2.3.4.md) installs AtFlows 0.1.1 by default,
offers optional AtMem-owned login for both dashboards, and adds an opt-in,
read-only review-lead handoff. AtBot remains 0.1.0.

## Previous beta
[AtMem 2.3.4b1](https://github.com/aetna000/atmem/blob/main/docs/releases/v2.3.4b1.md) improved retrieval efficiency and
session navigation while preserving authority and evidence boundaries.

## Upgrade checklist
1. Stop writers or create a verified Home snapshot.
2. Follow the exact install/upgrade commands in the release note.
3. Upgrade the OpenClaw bridge if connected and restart long-running clients.
4. Verify the Home and control state before relying on fresh evidence.
5. Keep the backup until validation finishes.

## Previous releases
- [2.3.2](../releases/v2.3.2.md)
- [2.3.1](../releases/v2.3.1.md)
- [2.3.0](../releases/v2.3.0.md)
- [2.2.6](../releases/v2.2.6.md)

Historical notes describe their own release, not the latest default behavior.
