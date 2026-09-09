#!/usr/bin/env node
/**
 * The plugin manifest must agree with the package and with the code.
 *
 * `openclaw.plugin.json` is what OpenClaw actually reads: `openclaw plugins
 * inspect` reports *its* version, and the AtMem installer refuses an upgrade
 * whose reported version does not match the pin. So a manifest left behind at
 * the previous version does not fail loudly at publish time -- it fails later,
 * on a user's machine, as "OpenClaw retained bridge <old>" after an install
 * that otherwise looked successful. 2.2.6-beta.4 shipped exactly that way.
 *
 * The same applies to `contracts.tools`: a tool the code registers but the
 * manifest omits is a tool a user cannot rely on being surfaced.
 *
 * Three declarations, one truth, checked here so a release cannot separate them.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const root = path.join(import.meta.dirname, "..");
const manifest = JSON.parse(readFileSync(path.join(root, "openclaw.plugin.json"), "utf8"));
const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
const index = readFileSync(path.join(root, "index.ts"), "utf8");
const readme = readFileSync(path.join(root, "README.md"), "utf8");

// --- version agreement -----------------------------------------------------

assert.equal(
  manifest.version,
  pkg.version,
  `openclaw.plugin.json says ${manifest.version} but package.json says ${pkg.version}. ` +
    "OpenClaw reports the manifest version, so a mismatch makes `atmem openclaw " +
    "upgrade` fail with \"retained bridge <old>\" after a successful install.",
);

assert.ok(
  readme.includes(pkg.version),
  `README.md does not mention ${pkg.version}; it documents the bridge users install.`,
);

// The Python installer pins the exact version it will accept. If that pin and
// the manifest disagree, every upgrade fails closed -- correctly, but only
// after a user hits it.
const installer = readFileSync(
  path.join(root, "..", "..", "atmem", "openclaw_install.py"),
  "utf8",
);
const pinned = /OPENCLAW_PLUGIN_VERSION\s*=\s*"([^"]+)"/.exec(installer)?.[1];
assert.equal(
  pinned,
  manifest.version,
  `atmem/openclaw_install.py pins ${pinned} but the manifest is ${manifest.version}. ` +
    "The installer verifies the manifest version against this pin.",
);

// --- tool contract agreement ----------------------------------------------

const registered = [...index.matchAll(/name:\s*"([a-z_]+)"/g)]
  .map((match) => match[1])
  .filter((name) => name.startsWith("memory_") || name.startsWith("atmem_") || name.startsWith("task_"));

const declared = new Set(manifest.contracts.tools);
const undeclared = [...new Set(registered)].filter((name) => !declared.has(name));
assert.deepEqual(
  undeclared,
  [],
  `index.ts registers ${JSON.stringify(undeclared)} but openclaw.plugin.json does not ` +
    "declare them. A tool the manifest omits is one a user cannot rely on being surfaced.",
);

// Amendment A's tools specifically: without these the feature is unreachable
// from inside OpenClaw no matter what the runtime supports.
for (const name of ["task_report_progress", "task_binding_status"]) {
  assert.ok(declared.has(name), `manifest does not declare ${name}`);
}

console.log(
  `manifest: version ${manifest.version} agrees with package, installer pin and README; ` +
    `${declared.size} tools declared, all registered tools covered`,
);
