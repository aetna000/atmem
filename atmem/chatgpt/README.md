# AtMem ChatGPT memory plugin

This package serves the hosted MCP API and the browser pages for AtMem account sign-in, OAuth consent, and memory approvals. The MCP API gives ChatGPT and Codex access to the user's AtMem Cloud account. Firebase Auth verifies accounts, and Firestore stores encrypted memory and OAuth state.

| What you need | Where to find it |
| --- | --- |
| MCP server and OAuth discovery | [`server.py`](server.py) |
| Sign-in, consent, and callback handoff | [`web.py`](web.py) and [`assets/web-consent.js`](assets/web-consent.js) |
| OAuth code and token handling | [`auth.py`](auth.py) and [`repository.py`](repository.py) |
| Plugin manifests, logos, and skill | [`plugins/atmem-chatgpt/`](../../plugins/atmem-chatgpt/) |
| Exact ChatGPT submission ZIP and manifest for v0.1.2 | [Submission archive at `fd3681d`](https://github.com/aetna000/atmem/tree/fd3681d/docs/chatgpt/submissions/0.1.2) |
| Deployment and rollback | [Cloud Run deployment guide](../../deploy/chatgpt/README.md) and [operations guide](../../docs/chatgpt/OPERATIONS.md) |
| OAuth repair and verification history | [OAuth login repair](../../docs/chatgpt/oauth-login-repair.md) |

## Hosted service

Cloud Run service `atmem-chatgpt` runs in project `atmemai`, region `us-central1`. The [MCP endpoint](https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/mcp) uses Streamable HTTP with OAuth. The [account sign-in page](https://atmem-chatgpt-nvwvv4d7sa-uc.a.run.app/login) signs users into AtMem. For review scans, use **Reconnect** from the plugin's MCP card to start the OAuth flow, then **Rescan** after authorization succeeds.

The `chatgpt-plugin-2026-11-21` Git tag marks the integration into `main`. Commit `da2246b` is the source for the browser handoff deployment `atmem-chatgpt-oauth-da2246b`. Check the [Cloud Run service](https://console.cloud.google.com/run/detail/us-central1/atmem-chatgpt/revisions?project=atmemai) for the current revision. Package publication and Cloud Run deployment are independent operations. Use the archived ZIP to inspect the exact v0.1.2 submission, since the working manifests are for development.

When deploying an image, preserve the existing Cloud Run settings and pinned Secret Manager references. Keep reviewer credentials, production secrets, and user data outside Git and the plugin bundle.

## Run the integration tests

From the repository root, with Python 3.12, Java 21, Node.js 22, and Firebase CLI available:

```sh
python -m pip install '.[chatgpt,dev]' pytest-asyncio
npm ci --prefix tests/chatgpt/browser
npm exec --prefix tests/chatgpt/browser -- playwright install chromium
firebase emulators:exec --only auth,firestore --project demo-atmem-plugin \
  --config deploy/chatgpt/firebase.emulator.json \
  'python -m pytest tests/chatgpt tests/test_chatgpt_oauth_atomic.py -q'
```

The suite includes a Chromium test that follows a cross-origin redirect after consent and checks that the form submits only once. To verify the actual review portal, complete **Reconnect** and confirm that **Rescan** reports a fresh result. A direct MCP check verifies the backend OAuth flow.
