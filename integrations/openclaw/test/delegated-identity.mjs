import assert from "node:assert/strict";
import { delegatedIdentity } from "../dist/src/delegated-identity.js";

const workspace = "/isolated/operator";
const config = { userId: "operator", requireOwner: true };
assert.equal(delegatedIdentity(config, {}).reason, "delegated_owner_metadata_missing");
assert.equal(delegatedIdentity(config, { senderIsOwner: false }).userId, undefined);
assert.equal(delegatedIdentity(config, { senderIsOwner: true }).userId, "operator");
assert.equal(delegatedIdentity({ ...config, requireOwner: false }, {}).userId, undefined);
const local = { ...config, requireOwner: false, localOperator: {
  isolated: true, agentId: "main", workspaceDir: workspace, sessionKey: "local", sessionId: "epoch-1",
} };
const ctx = { agentId: "main", workspaceDir: workspace, sessionKey: "local", sessionId: "epoch-1",
  runId: "turn-1", messageProvider: "cli" };
assert.equal(delegatedIdentity(local, ctx, workspace).userId, "operator");
assert.equal(delegatedIdentity({ ...local, requireOwner: true }, ctx, workspace).userId, undefined);
for (const field of ["agentId", "workspaceDir", "sessionKey", "sessionId", "runId", "messageProvider"]) {
  assert.equal(delegatedIdentity(local, { ...ctx, [field]: undefined }, workspace).userId, undefined, field);
}
for (const patch of [
  { agentId: "other" }, { workspaceDir: "/other" }, { sessionKey: "other" }, { sessionId: "epoch-2" },
  { messageProvider: "discord" }, { channel: "discord" }, { channelId: "shared" },
  { senderId: "another-user" }, { chatId: "shared" }, { accountId: "shared" },
  { senderIsOwner: false }, { senderIsOwner: "true" },
]) assert.equal(delegatedIdentity(local, { ...ctx, ...patch }, workspace).userId, undefined, JSON.stringify(patch));
assert.equal(delegatedIdentity(local, ctx, "/another-workspace").userId, undefined);
assert.equal(delegatedIdentity(local, ctx).userId, undefined);
assert.equal(delegatedIdentity({ ...local, localOperator: { ...local.localOperator, isolated: false } }, ctx, workspace).userId, undefined);
console.log("delegated identity: default ownership, isolated CLI scope, channel and cross-scope refusal passed");

const { isolatedCliProcess } = await import("../dist/src/delegated-identity.js");
const { mkdtempSync, chmodSync, rmSync, symlinkSync } = await import("node:fs");
const { tmpdir } = await import("node:os");
const { join } = await import("node:path");
const privateRoot = mkdtempSync(join(tmpdir(), "atmem-local-identity-"));
try {
  const mapping = { ...local, localOperator: { ...local.localOperator, stateDir: privateRoot } };
  const runtime = { argv: ["agent", "--local"], stateDir: privateRoot, uid: process.getuid() };
  assert.equal(isolatedCliProcess(mapping, {}, runtime), true);
  assert.equal(isolatedCliProcess(mapping, { channels: { discord: { enabled: false } } }, runtime), false);
  for (const argv of [["gateway"], ["agent"], ["agent", "--local", "--deliver"], ["agent", "--local", "--channel=discord"]]) {
    assert.equal(isolatedCliProcess(mapping, {}, { ...runtime, argv }), false);
  }
  assert.equal(isolatedCliProcess(mapping, {}, { ...runtime, stateDir: "/different" }), false);
  assert.equal(isolatedCliProcess(mapping, {}, { ...runtime, uid: runtime.uid + 1 }), false);
  assert.equal(isolatedCliProcess(mapping, undefined, runtime), false);
  chmodSync(privateRoot, 0o755);
  assert.equal(isolatedCliProcess(mapping, {}, runtime), false);
  chmodSync(privateRoot, 0o700);
  const noOrigin = { ...ctx, messageProvider: undefined };
  assert.equal(delegatedIdentity(mapping, noOrigin, workspace, true).userId, "operator");
  assert.equal(delegatedIdentity(mapping, noOrigin, workspace, false).userId, undefined);
  assert.equal(delegatedIdentity(mapping, { ...noOrigin, channel: "discord" }, workspace, true).userId, undefined);
  assert.equal(delegatedIdentity(mapping, { ...noOrigin, senderIsOwner: false }, workspace, true).userId, undefined);
} finally { rmSync(privateRoot, { recursive: true, force: true }); }
console.log("isolated CLI process: private directory, explicit invocation and channel isolation passed");
