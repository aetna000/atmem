import path from "node:path";
import { lstatSync, realpathSync } from "node:fs";
import type { OpenClawHookCtx } from "./types.js";

export interface DelegatedIdentityConfig {
  userId: string;
  requireOwner: boolean;
  localOperator?: {
    isolated: boolean;
    stateDir?: string;
    agentId: string;
    workspaceDir: string;
    sessionKey: string;
    sessionId: string;
  };
}

/** Verify the dedicated CLI process when the host omits origin metadata.
 * This is an explicit local operator trust boundary, never shared-channel auth.
 */
export function isolatedCliProcess(
  config: DelegatedIdentityConfig,
  hostConfig: Record<string, unknown> | undefined,
  runtime = { argv: process.argv.slice(2), stateDir: process.env.OPENCLAW_STATE_DIR, uid: process.getuid?.() },
): boolean {
  const local = config.localOperator;
  if (!local?.isolated || !local.stateDir || !runtime.stateDir || !hostConfig) return false;
  if (!runtime.argv.includes("agent") || !runtime.argv.includes("--local")) return false;
  const routed = ["--deliver", "--channel", "--to", "--reply-channel", "--reply-to", "--reply-account"];
  if (runtime.argv.some(arg => routed.some(flag => arg === flag || arg.startsWith(flag + "=")))) return false;
  const channels = hostConfig.channels;
  if (channels !== undefined && (!channels || typeof channels !== "object" || Array.isArray(channels) || Object.keys(channels).length)) return false;
  try {
    const directory = lstatSync(local.stateDir);
    return path.isAbsolute(local.stateDir) && directory.isDirectory() && !directory.isSymbolicLink()
      && (directory.mode & 0o077) === 0 && directory.uid === runtime.uid
      && realpathSync(local.stateDir) === realpathSync(runtime.stateDir);
  } catch { return false; }
}

/** Host metadata and operator configuration only; never prompt/model input. */
export function delegatedIdentity(
  config: DelegatedIdentityConfig,
  ctx: OpenClawHookCtx,
  configuredWorkspace?: string,
  verifiedIsolatedProcess = false,
): { userId?: string; reason?: string } {
  if (!config.userId) return { reason: "delegated_user_unconfigured" };
  if (ctx.senderIsOwner === false) return { reason: "delegated_sender_not_owner" };
  if (ctx.senderIsOwner !== undefined && ctx.senderIsOwner !== true) {
    return { reason: "delegated_owner_metadata_invalid" };
  }
  if (config.requireOwner) {
    return ctx.senderIsOwner === true
      ? { userId: config.userId }
      : { reason: "delegated_owner_metadata_missing" };
  }
  // Legacy requireOwner:false is no longer an unrestricted identity bypass.
  const local = config.localOperator;
  if (!local || local.isolated !== true) {
    return { reason: "delegated_local_isolation_required" };
  }
  if ((ctx.messageProvider !== "cli" && !(ctx.messageProvider === undefined && verifiedIsolatedProcess)) || ctx.channel || ctx.channelId ||
      ctx.accountId || ctx.chatId || ctx.senderId) {
    return { reason: "delegated_local_origin_unverified" };
  }
  if (!local.agentId || !local.sessionKey || !local.sessionId || !local.workspaceDir ||
      !ctx.runId || !ctx.workspaceDir || !configuredWorkspace ||
      !path.isAbsolute(local.workspaceDir) || !path.isAbsolute(ctx.workspaceDir) ||
      !path.isAbsolute(configuredWorkspace) ||
      ctx.agentId !== local.agentId || ctx.sessionKey !== local.sessionKey ||
      ctx.sessionId !== local.sessionId ||
      path.resolve(ctx.workspaceDir) !== path.resolve(local.workspaceDir) ||
      path.resolve(configuredWorkspace) !== path.resolve(local.workspaceDir)) {
    return { reason: "delegated_local_scope_mismatch" };
  }
  return { userId: config.userId };
}
