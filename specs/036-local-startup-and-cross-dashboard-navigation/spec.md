# Local startup and cross-dashboard navigation

**Status:** Implemented for AtMem 2.3.6.
**Companion contracts:** AtFlows `specs/009-cross-dashboard-navigation`; website `specs/005-cross-dashboard-consistency`.

## Overview

Make `pip install atmem`, `atmem init`, and `atmem status` the short local path to an inspectable AtMem, AtBot, and AtFlows installation. Keep the applications separate in authority and storage while linking their dashboards when a verified local endpoint exists. Align the AtMem header lockup with the published AtMem.ai 20 px mark and compact wordmark.

## User scenarios

1. On a fresh install, `atmem init` creates the local account, starts AtMem, configured AtBot, and installed AtFlows, reports actual URLs, and shows explicit errors for any unavailable component. It does not activate memory influence or egress.
2. After an upgrade, `atmem init` preserves account/data, refreshes only AtMem-managed processes to installed versions, and reports stale independent processes without taking them over.
3. A signed-in user can move from AtMem to a verified running AtFlows dashboard and back without guessing ports. Each app still enforces its own authentication contract.
4. `atmem status` shows installed and running versions, service health, selected ports, auth mode, and adapter mismatch without falsely claiming capture or delivery proof.

## Requirements

- **FR-001:** `atmem init` MUST be idempotent and start/refresh the local AtMem dashboard; `--no-open` suppresses browser launch, not service startup.
- **FR-002:** If installed and prerequisites are met, init MUST start AtFlows with AtMem delegated local login, select available loopback ports, and report both dashboard and proxy URLs. It MUST NOT adopt, stop, or silently relabel independent AtFlows processes.
- **FR-003:** Init MUST start configured AtBot when safe, show fallback/failure state, and never claim optional companion success when it failed.
- **FR-004:** Status MUST distinguish package version from running version and show actionable repair guidance for stale AtMem/AtFlows/OpenClaw bridge, unavailable Bun, port conflict, and unsupported host state.
- **FR-005:** AtMem MUST show an AtFlows link in the persistent top navigation only when a running local dashboard URL has been validated. The UI MUST use the reported port, not a fixed default, and MUST never turn untrusted input into a navigation target.
- **FR-006:** AtMem header MUST use the AtMem.ai mark and compact 20 px/approximately 16 px lockup; links MUST remain keyboard-operable and visible in light/dark modes.
- **FR-007:** No startup or navigation endpoint may disclose a secret or bypass AtMem/AtFlows authorization. Canonical memory and telemetry stores remain separate.
- **FR-008:** Documentation and release notes MUST distinguish published 2.3.4 manual AtFlows startup from this unreleased automatic workflow, then update at release.
- **FR-009:** The AtMem dashboard browser title MUST be `AtMem.ai | Insight` and its favicon MUST use the same memory-mark geometry and teal as the website and AtFlows.

## Success criteria

- **SC-001:** Isolated fresh-install and upgrade tests verify preserved account/data, current managed process versions, real ports, and no silent optional failure.
- **SC-002:** Tests verify independent AtFlows remains untouched and stale OpenClaw bridge status is not reported as healthy.
- **SC-003:** Browser or DOM tests verify the link appears only for a valid running loopback dashboard and header scale matches website tokens.
- **SC-004:** CLI JSON/text, installed-artifact, Python, companion, and OpenClaw gates pass before release; no claim of release is made before external publishing is verified.
- **SC-005:** Browser-tab test verifies the exact title and an SVG memory-mark favicon; no generic browser globe remains.

## Exclusions

No automatic OpenClaw adapter repair or activation, forced takeover of an independent AtFlows instance, merged databases, remote dashboard discovery, or website production deployment from a feature branch.
