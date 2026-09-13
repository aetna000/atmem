/** Retain a bounded diagnostic, never the full tool result or stack trace. */
export function toolErrorReason(value: unknown): string | undefined {
  let text: unknown = value;
  if (value && typeof value === "object") {
    const row = value as Record<string, unknown>;
    text = row.error ?? row.message;
    if (text && typeof text === "object") text = (text as Record<string, unknown>).message;
    if (text === undefined && Array.isArray(row.content)) {
      text = row.content.find(item => item?.type === "text" && typeof item.text === "string")?.text;
    }
  }
  if (typeof text !== "string" || !text.trim()) return undefined;
  const bounded = text.slice(0, 8192);
  // OpenClaw wraps thrown web errors as untrusted API content. Extract only
  // its narrow status prefix, never the page text or instructions beneath it.
  if (bounded.startsWith("SECURITY NOTICE:")) {
    const status = bounded.match(/<<<EXTERNAL_UNTRUSTED_CONTENT id="[a-f0-9]+">>>\r?\nSource: API\r?\n---\r?\n(Web fetch failed \([1-5][0-9]{2}\)):/);
    return status?.[1];
  }
  return bounded.split(/[\r\n]/, 1)[0]
    .replace(/https?:\/\/[^\s<>]+/gi, "[redacted-url]")
    .replace(/\b(?:Bearer|Basic)\s+\S+/gi, "[redacted-auth]")
    .replace(/\b(?:api[_-]?key|token|password|passwd|secret|authorization|cookie)\s*[:=]\s*(?:"[^"]*"|'[^']*'|\S+)/gi, "[redacted-credential]")
    .replace(/\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+/g, "[redacted-token]")
    .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g, "[redacted-email]")
    .replace(/(?:[A-Za-z]:\\|\/)[^\s<>"']+/g, "[redacted-path]")
    .replace(/"[^"\r\n]*"|'[^'\r\n]*'/g, "[redacted-value]")
    .replace(/[\x00-\x1f\x7f]/g, " ").trim().slice(0, 512) || undefined;
}
