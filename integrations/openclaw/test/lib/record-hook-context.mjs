#!/usr/bin/env node
/**
 * Record the resolved OpenClaw's hook-context shape as a fixture.
 *
 * Usage: node test/lib/record-hook-context.mjs [--label min|lockfile|latest]
 *
 * Run this when adding a version to the compatibility matrix, or when a
 * reviewed upstream change moves the shape. Never run it to silence a failing
 * check: a diff in these fixtures is the signal T058 exists to produce.
 */
import { writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { readHookContextShape } from "./hook-context-shape.mjs";

const labelIndex = process.argv.indexOf("--label");
const label = labelIndex > -1 ? process.argv[labelIndex + 1] : null;
const shape = readHookContextShape();
const dir = path.join(import.meta.dirname, "..", "fixtures", "hook-context");
mkdirSync(dir, { recursive: true });
const file = path.join(dir, `${shape.version}.json`);
writeFileSync(file, `${JSON.stringify({ label, ...shape }, null, 2)}\n`);
console.log(`recorded ${path.relative(process.cwd(), file)} (openclaw ${shape.version})`);
