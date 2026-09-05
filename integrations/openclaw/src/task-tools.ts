/**
 * Model- and owner-facing governed task tools.
 *
 * Spec 007 Amendment A, FR-049 path (b) and FR-050.
 *
 * A manager method and an MCP operation are invisible to a model. For an agent
 * to report progress at all, a tool has to be registered with the host through
 * the same mechanism that publishes `memory_search`. That is what this file is.
 *
 * Two audiences, deliberately separated:
 *
 *  - `task_*` tools the model calls. They resolve through the conversation's
 *    own binding, so a model can only affect the task its conversation is bound
 *    to, and every outcome is reported back in words the model can act on -- a
 *    rejection it cannot interpret is a rejection it will retry blindly.
 *  - `task_bind` / `task_unbind` / `task_binding_status`, which an operator
 *    runs from inside the conversation. These are gated on the host's own owner
 *    signal. That signal is optional upstream, so anything other than an
 *    explicit `true` is treated as *not* the owner: absence is never permission.
 */

import type { AtmemSessionIdentity, OpenClawPluginToolContext } from "./types.js";

/** The one place identity is derived, so no caller can assemble a partial one. */
export function sessionIdentityForTool(
  ctx: OpenClawPluginToolContext,
): AtmemSessionIdentity | undefined {
  const sessionKey = ctx.sessionKey ?? ctx.sessionId;
  const sessionEpoch = ctx.sessionId;
  if (!sessionKey || !sessionEpoch) return undefined;
  return {
    host_type: "openclaw",
    session_key: sessionKey,
    session_epoch: sessionEpoch,
  };
}

/** Absence is never permission. Only an explicit affirmative is the owner. */
export function isConversationOwner(ctx: OpenClawPluginToolContext): boolean {
  return ctx.senderIsOwner === true;
}

/**
 * Turn one AtMem decision into something a model can act on.
 *
 * The outcome vocabulary is small and each value implies a different next
 * move, so saying which one it is matters more than saying it failed.
 */
export function describeDecision(result: Record<string, unknown>): string {
  const outcome = String(result.outcome ?? "");
  const reasons = Array.isArray(result.reason_codes)
    ? (result.reason_codes as string[]).join(", ")
    : String(result.reason_code ?? "");
  switch (outcome) {
    case "accepted":
      return `Recorded. The task is now at revision ${result.resulting_revision}.`;
    case "no_change":
      return `No change: the task already reflects this (${reasons}).`;
    case "conflict":
      return (
        `Conflict: the task moved while you were working (${reasons}). ` +
        "Read it again with task_state and submit against the revision you get back."
      );
    case "rejected":
      return `Rejected (${reasons}). Do not retry this unchanged; the reason explains what AtMem will accept.`;
    default:
      break;
  }
  if (result.reason_code) {
    return `Not applied (${result.reason_code}): ${String(result.message ?? "")}`;
  }
  return String(result.message ?? "No decision was returned.");
}

/** A refusal shaped like every other tool result, so a model reads one thing. */
export function refusal(message: string): {
  content: { type: "text"; text: string }[];
} {
  return {
    content: [{ type: "text", text: JSON.stringify({ ok: false, message }) }],
  };
}

export function ok(payload: Record<string, unknown>): {
  content: { type: "text"; text: string }[];
} {
  return {
    content: [{ type: "text", text: JSON.stringify({ ok: true, ...payload }) }],
  };
}

export const NOT_OWNER_MESSAGE =
  // Identical whether a binding exists or not: a non-owner must not be able to
  // learn what this conversation is bound to by asking.
  "Only the owner of this conversation can manage its governed task binding.";

export const NO_IDENTITY_MESSAGE =
  "This conversation has no usable session identity, so AtMem cannot tell " +
  "which conversation it is. No task binding can be resolved or created.";
