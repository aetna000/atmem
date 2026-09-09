/**
 * Read the declared plugin hook-context surface from an installed OpenClaw.
 *
 * Spec 007 Amendment A, T058. Two premises decide whether the amendment is
 * needed and whether its design works:
 *
 *   1. No hook context supplies a governed task identity, so the bridge's
 *      `ctx.taskId` branch (index.ts) never runs and delivery requires the
 *      operator-registered binding FR-042 adds.
 *   2. Every hook the amendment resolves identity in supplies `sessionId`,
 *      the value FR-052 binds as `session_epoch`.
 *
 * Both are recorded per version as fixtures rather than asserted once, so a
 * host that later changes either one produces a reviewable diff instead of a
 * silent wrong answer. A host that starts supplying task identity re-scopes
 * the amendment toward FR-043's first resolution step; a hook that stops
 * supplying `sessionId` invalidates the epoch design at that hook.
 *
 * This reads the *declared* surface from the resolved package's type
 * definitions. It is not runtime proof: a declaration says what a host promises
 * to pass, not what it passes. Runtime behaviour of the identity we rely on is
 * proven separately by the epoch-rotation test (T078). Read only from a
 * resolved dependency path — never from a globally installed OpenClaw, whose
 * version CI cannot control.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

/** Field names that would mean the host selects a governed task for us. */
export const TASK_IDENTITY_FIELDS = ["taskId", "task_id", "governedTaskId", "atmemTaskId"];

/**
 * Contexts the in-host binding surface (FR-050) runs under. The owner signal
 * lives here and not on hook contexts, which is why T076's bind/unbind/status
 * must be a command or tool rather than a hook.
 */
export const OWNER_GATED_CONTEXTS = ["OpenClawPluginToolContext", "PluginCommandContext"];

/** Hooks Amendment A resolves task identity in or submits observations from. */
export const AMENDMENT_HOOKS = [
  "before_prompt_build",
  "llm_input",
  "agent_end",
  "after_tool_call",
  "before_reset",
  "session_start",
  "session_end",
];

/**
 * Where to start looking for a resolvable OpenClaw. `OPENCLAW_PROBE_DIR` lets
 * CI point the check at one isolated matrix install per job without touching
 * the bridge's own `node_modules`. It names a directory to search *from*, so an
 * empty or wrong value fails to resolve rather than silently reaching a global
 * install.
 */
function probeRoot() {
  return process.env.OPENCLAW_PROBE_DIR || import.meta.dirname;
}

/**
 * Resolve the installed openclaw package directory by walking `node_modules`
 * upward from `from`. Deliberately not `require.resolve`: the package does not
 * export `package.json`, and a resolver that falls back to a global install
 * would defeat the point of pinning the version under test.
 */
export function resolveOpenClawDir(from = probeRoot()) {
  let dir = from;
  for (;;) {
    const candidate = path.join(dir, "node_modules", "openclaw");
    if (existsSync(path.join(candidate, "package.json"))) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

export function readOpenClawVersion(packageDir) {
  return JSON.parse(readFileSync(path.join(packageDir, "package.json"), "utf8")).version;
}

/**
 * Extract the top-level field names of `typeName` from a d.ts body.
 * Brace-matched rather than regex-scanned so nested object types cannot
 * terminate the block early, and depth-tracked so a nested type's fields are
 * never mistaken for this type's own.
 */
function extractTypeFields(source, typeName) {
  const header = `type ${typeName} = {`;
  const start = source.indexOf(header);
  if (start === -1) return null;
  const open = start + header.length - 1;
  let depth = 0;
  let end = -1;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    else if (source[i] === "}") {
      depth -= 1;
      if (depth === 0) { end = i; break; }
    }
  }
  if (end === -1) return null;

  const fields = [];
  let nesting = 0;
  for (const rawLine of source.slice(open + 1, end).split("\n")) {
    if (nesting === 0) {
      // Optionality is recorded, never discarded. A declaration of `sessionId?`
      // says the host *may* supply it, which is a different premise from `it
      // does` -- and the difference decides whether FR-052 can rely on it.
      const match = /^(?:readonly\s+)?([A-Za-z_$][\w$]*)(\?)?\s*:/.exec(rawLine.trim());
      if (match) fields.push({ name: match[1], optional: Boolean(match[2]) });
    }
    for (const ch of rawLine) {
      if (ch === "{") nesting += 1;
      else if (ch === "}") nesting -= 1;
    }
  }
  return fields;
}

/** Map each amendment hook to the context type name OpenClaw passes it. */
function extractHookContexts(sources) {
  const contexts = {};
  for (const source of sources) {
    for (const hook of AMENDMENT_HOOKS) {
      if (contexts[hook]) continue;
      const match = new RegExp(`^\\s+${hook}:\\s*\\(event:[^,]+,\\s*ctx:\\s*(\\w+)\\)`, "m")
        .exec(source);
      if (match) contexts[hook] = match[1];
    }
  }
  return contexts;
}

/** The declared hook-context shape of the OpenClaw resolved at `from`. */
export function readHookContextShape(from = probeRoot()) {
  const packageDir = resolveOpenClawDir(from);
  if (!packageDir) {
    throw new Error(
      "no resolvable `openclaw` dependency; run `npm ci` in integrations/openclaw. " +
        "This check must never fall back to a globally installed OpenClaw.",
    );
  }
  const version = readOpenClawVersion(packageDir);
  const distDir = path.join(packageDir, "dist");
  const sources = readdirSync(distDir)
    .filter((name) => name.endsWith(".d.ts"))
    .map((name) => readFileSync(path.join(distDir, name), "utf8"));

  const hookContexts = extractHookContexts(sources);
  const types = {};
  const wanted = new Set([...Object.values(hookContexts), ...OWNER_GATED_CONTEXTS]);
  for (const typeName of wanted) {
    for (const source of sources) {
      const fields = extractTypeFields(source, typeName);
      if (fields) {
        types[typeName] = fields.slice().sort((a, b) => a.name.localeCompare(b.name));
        break;
      }
    }
  }
  return { version, hookContexts, types };
}

function findField(shape, typeName, fieldName) {
  return (shape.types[typeName] ?? []).find((field) => field.name === fieldName) ?? null;
}

/** Task-identity fields declared on any context an amendment hook receives. */
export function taskIdentityFieldsIn(shape) {
  const found = new Set();
  for (const [typeName, fields] of Object.entries(shape.types)) {
    if (OWNER_GATED_CONTEXTS.includes(typeName)) continue;
    for (const field of fields) {
      if (TASK_IDENTITY_FIELDS.includes(field.name)) found.add(field.name);
    }
  }
  return [...found].sort();
}

/** Owner-gated contexts that do not declare `senderIsOwner` at all. */
export function ownerContextsMissingSignal(shape) {
  return OWNER_GATED_CONTEXTS.filter(
    (typeName) => findField(shape, typeName, "senderIsOwner") === null,
  );
}

/** Amendment hooks whose context does not declare `field` at all. */
export function hooksMissingField(shape, field) {
  return AMENDMENT_HOOKS.filter((hook) => {
    const typeName = shape.hookContexts[hook];
    return !typeName || findField(shape, typeName, field) === null;
  });
}

/**
 * Amendment hooks where `field` is declared but optional.
 *
 * These are the hooks where the host may legally pass nothing. They are not a
 * failure -- they are the set the adapter must fail closed on, so it is
 * reported rather than asserted empty.
 */
export function hooksWithOptionalField(shape, field) {
  return AMENDMENT_HOOKS.filter((hook) => {
    const typeName = shape.hookContexts[hook];
    return Boolean(typeName) && findField(shape, typeName, field)?.optional === true;
  });
}

/** Owner-gated contexts where `senderIsOwner` is declared but optional. */
export function ownerContextsWithOptionalSignal(shape) {
  return OWNER_GATED_CONTEXTS.filter(
    (typeName) => findField(shape, typeName, "senderIsOwner")?.optional === true,
  );
}
