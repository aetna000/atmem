# Releases and upgrades

## Stable release
[AtMem 2.3.6](../releases/v2.3.6.md) adds canonical secret refusal,
direct-parent taint propagation, issued procedure-review authority, and
portable Windows-safe locking. Its candidate passed 400/400 representable
Memory Integrity Benchmark trials with zero failures or errors; the upstream
position remains provisional until accepted.

[AtMem 2.3.5](../releases/v2.3.5.md) introduced the one-command companion
startup path: it installs AtFlows 0.1.2, starts and checks
the local dashboards and AtBot through `atmem init`, and reports actual URLs
and startup problems through `atmem status`. AtBot remains 0.1.0. Trace
collection and the read-only AtFlows review-lead handoff remain explicit.

## Previous release
[AtMem 2.3.4](../releases/v2.3.4.md) added the separate AtFlows companion and optional shared login.

## Upgrade checklist
1. Stop writers or create a verified Home snapshot.
2. Follow the exact install/upgrade commands in the release note.
3. Upgrade the OpenClaw bridge if connected and restart long-running clients.
4. Verify the Home and control state before relying on fresh evidence.
5. Keep the backup until validation finishes.

## Previous releases
- [2.3.6 beta history](https://github.com/aetna000/atmem/blob/main/docs/releases/v2.3.6b1.md)
- [2.3.4 beta history](https://github.com/aetna000/atmem/blob/main/docs/releases/v2.3.4b1.md)
- [2.3.3](../releases/v2.3.3.md)
- [2.3.2](../releases/v2.3.2.md)
- [2.3.1](../releases/v2.3.1.md)
- [2.3.0](../releases/v2.3.0.md)
- [2.2.6](../releases/v2.2.6.md)

Historical notes describe their own release, not the latest default behavior.
