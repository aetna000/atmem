// Exact OpenClaw progress_card ↔ native relay equivalence. Never discard raw digests.
export function progressCardComparison(name: string, result: unknown, digest: (v: unknown) => string) {
  if (name !== "progress_card") return {};
  const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
  const keys = (v: Record<string, unknown>, expected: string[]) =>
    Object.keys(v).sort().join(",") === [...expected].sort().join(",");
  const native = Array.isArray(result);
  if (!native && (!record(result) || !keys(result, ["content", "details"]))) return {};
  const content = native ? result : (result as Record<string, unknown>).content;
  if (!Array.isArray(content) || content.length !== 2 || !content.every(v =>
    record(v) && keys(v, ["type", "text"]) && v.type === (native ? "input_text" : "text") &&
    typeof v.text === "string" && v.text.length <= 1024)) return {};
  let payload: unknown;
  try { payload = JSON.parse(content[1].text); } catch { return {}; }
  if (!record(payload) || !keys(payload, ["revision", "steps"])) return {};
  const { revision, steps } = payload;
  if (revision !== null && (!Number.isSafeInteger(revision) || (revision as number) < 1)) return {};
  if (steps !== null && (!record(steps) || !keys(steps, ["completed", "total"]) ||
    !Number.isSafeInteger(steps.completed) || !Number.isSafeInteger(steps.total) ||
    (steps.completed as number) < 0 || (steps.total as number) < 1 || (steps.total as number) > 50 ||
    (steps.completed as number) > (steps.total as number))) return {};
  if (revision === null && steps !== null) return {};
  const expected = revision === null ? "Progress card cleared" : steps === null
    ? `Progress card updated (rev ${revision})`
    : `Progress card updated (rev ${revision}, ${(steps as Record<string, unknown>).completed}/${(steps as Record<string, unknown>).total} done)`;
  if (content[0].text !== expected || content[1].text !== JSON.stringify(payload, null, 2)) return {};
  if (!native && digest((result as Record<string, unknown>).details) !== digest(payload)) return {};
  return {
    result_comparison_profile: "openclaw-progress-card-v1",
    result_comparison_sha256: digest(payload),
    result_observation_shape: native ? "native_input_text" : "tool_content_details",
  };
}
