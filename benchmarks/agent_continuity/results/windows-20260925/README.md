# Native Windows installation and UI acceptance — 25 September 2026

Tested through SSH on DESKTOP-3FO00QL, Windows 11 Pro x64, Python 3.12.6,
Microsoft Edge, AtMem-managed Bun 1.4.2. No WSL or Linux container.

Installed local development wheels into `C:\Users\user\AtMemWindowsTest\venv`:

- AtMem 2.3.7b2, SHA256 `6dcb5989f45eecf3c987286d9ef5e5e611610759be51ae09cfc51c37fa09a71e`.
- AtFlows 0.1.2, SHA256 `7ec2b1feef950e3841eb68db79d5ffdca36fc1492d6ab05825551949a948b04f`.
- Published AtBot 0.1.0 installed as dependency; no model provider configured.
- LangGraph 1.1.5 and SQLite checkpoint 3.0.3.

These are feature builds, not a newly published Windows release. AtMem contains
the Windows startup correction; AtFlows contains the schema startup-lock fix.

## Results

| Check | Result |
| --- | --- |
| Original installed product tests | 32 passed, 9 setup errors |
| After startup correction | 43 passed, 1 POSIX-only test skipped |
| Installed LangGraph process-kill recovery | Both receipt windows passed; one published document each |
| AtFlows product storage/accounting | 6 passed, 31 assertions, including competing writer at startup |
| AtMem login and Resume work | Passed in Windows Edge |
| AtFlows shared AtMem login and Resume work | Passed in Windows Edge |
| JavaScript page errors | None observed |
| Desktop/narrow viewport screenshots | 1440×1000 and 390×844, inspected |

The screenshots show empty-state UI, not invented agent activity. The process-kill
test uses a separate test authority, real file output containing the pinned public
tau2 README, an installed application, and stock LangGraph restart. It waits for
the actual lease, does not repair state, and produces one document per case.
This does not establish production-wide reliability or power-loss durability.

## Problems found and corrected

1. Home/control-state atomic writers called Unix-only `os.fchmod` on Windows.
   They now apply POSIX descriptor permissions only on POSIX, inside the file
   context so an error cannot leave its handle open during cleanup. Windows uses
   its directory ACLs. `test_windows_atomic_startup.py` covers this regression.
2. The acceptance rig read a UTF-8 artifact using Windows' default text encoding.
   The read now explicitly uses UTF-8. First attempt retained on the machine;
   successful `installed-crash.json` is the second attempt.
3. The AtFlows competing-writer test built an import from URL.pathname, which is
   not a Windows filesystem path. It now uses the file URL, and passes natively.

## Deployment constraints still open

The stock background processes did not survive SSH session termination. This
machine uses the limited-user, manually started scheduled task **AtMem Windows
Test Dashboards** to launch the normal `atmem init` and keep its parent alive.
This workaround is not claimed as a shipped daemon fix or reboot-autostart test.
The new Home was first created by an elevated SSH session; its ownership and
ACLs were corrected for the named Windows user before limited-user startup.
The product still needs a documented/evaluated elevated-to-standard-user story.

AtMem is listening on loopback8766; AtFlows dashboard1337 and proxy8080. No new
inbound firewall ports were opened. User credentials are retained only on the
Windows machine and are excluded from this bundle. AtBot model assistance stays
off; no OpenClaw integration or paid LLM run was performed.

Raw before/after JUnit XML, UI checks, screenshots and installed crash report are
kept here. Product fixes and this report are local changes pending commit/review.
