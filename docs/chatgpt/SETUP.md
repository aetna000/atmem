# Setup, connection, failure handling and uninstall

## Local real-storage test (no charges, no real memories)

Use a new venv from this feature checkout. Python 3.12 is the tested interpreter;
base AtMem's Python range is unchanged. Optional cloud SDKs are not base deps.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install '.[chatgpt,dev]' pytest-asyncio
```

Use the Firebase CLI and Java 21 for the emulators. Do not point this command at
a production project or change its demo- identifier. It launches real Auth and
Firestore emulators, starts a real authenticated HTTP MCP process and exercises
actual AtMem SQLCipher memory with synthetic users. No OpenAI API key or model
call is needed.

```sh
firebase emulators:exec --only auth,firestore \
  --project demo-atmem-plugin --config deploy/chatgpt/firebase.emulator.json \
  '.venv/bin/python -m pytest tests/chatgpt -q'
```

On Windows use a Python 3.12 venv's Scripts/python.exe and install the documented
SQLCipher runtime first. Native Windows execution of this new cloud service has
not yet been qualified; the emulator harness is qualified on macOS. The planned
production runtime is Linux/Cloud Run, not yet deployed or load-tested.

## Manual local server

```sh
python -m atmem.chatgpt init-test --directory /tmp/atmem-chatgpt-demo
firebase emulators:start --only auth,firestore --project demo-atmem-plugin \
  --config deploy/chatgpt/firebase.emulator.json
```

In a second terminal, using that venv:

```sh
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085
export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
python -m atmem.chatgpt serve --config /tmp/atmem-chatgpt-demo/config.json
```

The server is at http://127.0.0.1:8769/mcp and health at /health. The config
contains a provided PKCE test client with a loopback callback for a real MCP
client. It is not a ChatGPT callback. Repeated server startup reuses Firestore
state; repeating init-test on a nonempty directory refuses to overwrite keys.
Never copy an existing native memory home into this test directory.

The automated tests provision disposable Firebase Auth accounts via its emulator
REST API and complete OAuth code/PKCE, user approval and MCP tool calls. For manual
work create a synthetic Auth emulator account using its normal UI/admin API and
register the exact callback of your actual MCP Inspector/client in config.
No production signup or account import is performed by this application.

## ChatGPT web: owner's Pro 100 account

A local loopback URL is not reachable by ChatGPT web. Once an approved, tested
remote HTTPS service or supported Secure MCP Tunnel exists:

1. Record the exact plan label and account/workspace, surface and UTC time. Do
   not infer connector/write/publishing eligibility from the user-reported tier.
2. Open https://chatgpt.com/plugins, use the plus/Add custom MCP server flow if
   available, and record the actual options or exact rejection. Follow current
   official instructions rather than an old developer-mode/settings path.
3. Configure the real endpoint and OAuth, copying the actual client identifier
   and callback shown by the flow into the server's provided-client allowlist.
   Read the warning and grant only intended permissions. No static token in ZIP.
4. Inspect discovered tools. Install/select the plugin in a new chat with @.
5. Read a seeded synthetic memory, propose a unique save, approve it in the
   service-owned page, commit and inspect persistence directly using the isolated
   review account. Read it in a new selected-plugin chat; correct and forget it.
6. Test denied writes, revoked access, unavailable service, wrong account/scope
   and actual platform confirmation. Record tool exposed/not exposed, invoked/not
   invoked, permission rejected or backend failure separately.
7. Remove synthetic data and disconnect/revoke. Never use the owner's real
   memories for this evaluation. Do not relabel write tools as read to get access.

If writes are unavailable, retain/test the real backend write implementation,
complete read tests and document the exact account limitation. Do not promise
that publication will change it. The required host demo is a real recording of
this flow, not the backend emulator tests or a generated mockup.

## Failure and retry
- permission_rejected: actual token lacks the operation scope; request a supported
  reauthorization/permission path, do not retry as a read.
- independent_user_approval_required: open and review the exact approval link;
  no boolean in tool arguments can replace it.
- stale_record_requires_new_approval: reread, propose again and approve again.
- generation_conflict_retry_same_intent: retry the same ID/key after rereading;
  do not create another memory. No success is returned for the losing generation.
- backend_unavailable_retry_same_intent: store state is unknown to this call;
  inspect receipt/retry the same ID. Never assert it was saved from an error.
- 401: expired/revoked/wrong-resource auth. 403: origin/CSRF/approval failure.
  429: wait at least Retry-After. 503: backend unavailable. No local fallback may
  silently write to native stores.

## Uninstall/disconnect

Remove the development plugin/custom connection in the actual host and revoke
its OAuth grant. Stop the owned service/emulators. Disconnecting does not erase
stored memories. For data deletion, approve exact-record operations and retain
their receipts before removing the connection. Deleting a service/key is not a
verified forget operation and may prevent recovery. Remove only the dedicated
synthetic test directory when its data and key are no longer needed. Retention
in provider backups/ChatGPT copies follows their separate policies.

## Registration sign-in
For the cloud registration policy, set `access_policy` to `registered`. Enable
Firebase email/password sign-in and account registration for this project. Use
Firebase's actual email verification handler; verify actual delivery with a user-
controlled test mailbox before public launch. Start account linking from ChatGPT,
choose Register, acknowledge cloud data flow, use a 12+ character password and
verify the email. Return to sign-in (restart linking if its five-minute request
expired). Sign in and grant the displayed OAuth scopes. Each memory mutation
still requires a separately signed-in preview and approval. Verification resend
and password reset links are on the sign-in page. No separate application UI.
The invited policy remains available for closed pilots and synthetic reviewers.
