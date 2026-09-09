#!/usr/bin/env node
// Real bridge hooks -> real AtMem MCP -> authenticated HTTP provider -> signed
// decision -> exact llm_input -> verified closed flight. The host/model events
// are synthetic; this does not claim a private Storizon or live model test.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createInterface } from "node:readline";
import { createHash } from "node:crypto";
import plugin from "../dist/index.js";

const python = process.env.ATMEM_TEST_PYTHON || "python";
const command = process.env.ATMEM_TEST_COMMAND || "atmem";
const helper = process.env.ATMEM_PROVIDER_FIXTURE || path.resolve(import.meta.dirname, "../../../tools/smoke_delegated_transport.py");
const root = mkdtempSync(path.join(tmpdir(), "atmem-delegated-journey-"));
const env = { ...process.env, ATMEM_DELEGATED_CONFIG: path.join(root, "delegated.json") };
const provider = spawn(python, [helper, "--serve", root], { env, stdio: ["pipe", "pipe", "inherit"] });
const lines = createInterface({ input: provider.stdout });
const services = [];
try {
  const details = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("provider fixture startup timed out")), 15000);
    lines.once("line", line => { clearTimeout(timer); resolve(JSON.parse(line)); });
    provider.once("exit", code => { clearTimeout(timer); reject(new Error(`provider exited ${code}`)); });
  });
  process.env.ATMEM_DELEGATED_CONFIG = details.config_path;
  const hooks = new Map(), logs = [];
  plugin.register({
    pluginConfig: {
      command, dbPath: details.memory_db, subject: details.subject,
      controlPlane: { enabled: true, statePath: details.state_path },
      agentWorkspaces: { main: details.workspace },
      delegatedContext: { userId: "owner", requireOwner: true },
      recall: { enabled: true, timeoutMs: 5000 },
      persona: { enabled: false }, capture: { enabled: false }, tools: { enabled: false },
    },
    logger: { debug: x => logs.push(x), info: x => logs.push(x), warn: x => logs.push(x), error: x => logs.push(x) },
    on: (name, handler) => hooks.set(name, handler),
    registerTool() {}, registerService: service => services.push(service),
  });
  for (const scenario of ["inject", "withhold", "tool-complete", "tool-error", "tool-missing", "tool-cross-turn"]) {
    const decision = scenario === "withhold" ? "withhold" : "inject";
    const ctx = { agentId: "main", sessionKey: `hmac-${scenario}`, sessionId: `hmac-${scenario}`,
      runId: `hmac-${scenario}`, senderIsOwner: true };
    const prompt = decision === "inject" ? (details.fact || "Synthetic trip query for HMAC journey") : "withhold this synthetic turn";
    await hooks.get("before_model_resolve")({ prompt, runId: ctx.runId, historyMessages: [], imagesCount: 0, tools: [] }, ctx);
    const insertion = await hooks.get("before_prompt_build")({ prompt }, ctx);
    if (decision === "inject") {
      assert.equal(insertion?.prependContext, details.exact, JSON.stringify(logs));
      assert.equal(insertion?.appendContext, undefined);
    } else assert.equal(insertion, undefined, JSON.stringify(logs));
    await hooks.get("llm_input")({ runId: ctx.runId, sessionId: ctx.sessionId, provider: "fixture", model: "synthetic",
      prompt: decision === "inject" ? details.exact + "\n" + prompt : prompt, historyMessages: [], imagesCount: 0, tools: [] }, ctx);
    if (scenario.startsWith("tool-")) {
      for (const toolName of ["read", "exec"]) {
        const toolCallId = `${scenario}-${toolName}`;
        const toolCtx = { ...ctx, toolCallId };
        await hooks.get("before_tool_call")({ toolName, params: {} }, toolCtx);
        if (scenario !== "tool-missing") {
          await hooks.get("after_tool_call")({ toolName, params: {}, result: { observed: true },
            error: scenario === "tool-error" ? "fixture terminal error" : undefined },
            scenario === "tool-cross-turn" ? { ...toolCtx, runId: `${ctx.runId}-other` } : toolCtx);
        }
      }
    }
    await hooks.get("llm_output")({ runId: ctx.runId, sessionId: ctx.sessionId, provider: "fixture", model: "synthetic",
      assistantTexts: ["Synthetic completion."], usage: { input: 10, output: 2, total: 12 } }, ctx);
    await hooks.get("agent_end")({ runId: ctx.runId, success: true, messages: [] }, ctx);
    const check = spawnSync(command, ["blackbox", "verify", ctx.runId, "--state", details.state_path, "--json"], { env, encoding: "utf8" });
    assert.equal(check.status, 0, check.stderr + check.stdout);
    const report = JSON.parse(check.stdout);
    assert.equal(report.timeline_chain_valid, true);
    const complete = !["tool-missing", "tool-cross-turn"].includes(scenario);
    assert.equal(report.structurally_complete, complete, JSON.stringify(report));
    assert.equal(report.verdict, !complete ? "incomplete_evidence"
      : scenario === "tool-error" ? "completed_with_tool_errors" : "completed_successfully");
    const shown = report.timeline.filter(row => row.event_type === "context.injected");
    assert.equal(shown.length, decision === "inject" ? 1 : 0, JSON.stringify(logs));
    if (decision === "inject") assert.equal(shown[0].payload.context_sha256, createHash("sha256").update(details.exact).digest("hex"));
    assert.ok(!JSON.stringify(report).includes(prompt));
    assert.ok(!JSON.stringify(report).includes(details.exact));
  }
  if (details.provider_kind === "real-mem0-oss") {
    const searchLog = path.join(root, "mem0-searches.jsonl");
    const countSearches = () => existsSync(searchLog) ? readFileSync(searchLog, "utf8").trim().split("\n").filter(Boolean).length : 0;
    for (const role of ["non-owner", "missing-owner", "other-user", "other-workspace"]) {
      const roleHooks = new Map();
      plugin.register({
        pluginConfig: {
          command, dbPath: details.memory_db, subject: details.subject,
          controlPlane: { enabled: true, statePath: details.state_path },
          agentWorkspaces: { main: role === "other-workspace" ? path.join(root, "other") : details.workspace },
          delegatedContext: { userId: role === "other-user" ? "other-user" : "owner", requireOwner: true },
          recall: { enabled: true, timeoutMs: 15000 }, persona: { enabled: false },
          capture: { enabled: false }, tools: { enabled: false },
        },
        logger: { debug() {}, info() {}, warn() {}, error() {} },
        on: (name, handler) => roleHooks.set(name, handler),
        registerTool() {}, registerService: service => services.push(service),
      });
      const ctx = { runId: `role-${role}`, agentId: "main", sessionKey: `role-${role}`, sessionId: `role-${role}`,
        senderIsOwner: role === "missing-owner" ? undefined : role !== "non-owner" };
      const before = countSearches();
      const insertion = await roleHooks.get("before_prompt_build")({ prompt: details.fact }, ctx);
      assert.equal(insertion, undefined, role);
      assert.equal(countSearches(), before, `${role} must fail before Mem0 access`);
    }
    console.log("Mem0 role-play: non-owner, absent owner, other user and other workspace refused before provider access");
  }
  console.log("authenticated delegated OpenClaw inject/withhold: exact llm_input, one/zero deliveries, tool success/error closure and missing/cross-turn refusal passed");
} finally {
  for (const service of services) await service.stop?.();
  provider.stdin.end();
  await new Promise(resolve => {
    if (provider.exitCode !== null) return resolve();
    const timer = setTimeout(() => { provider.kill(); resolve(); }, 3000);
    provider.once("exit", () => { clearTimeout(timer); resolve(); });
  });
  lines.close();
  rmSync(root, { recursive: true, force: true });
}
