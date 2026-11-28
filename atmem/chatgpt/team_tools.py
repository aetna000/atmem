"""Optional account-bound MCP tools for a co-located AtMem team broker."""

import hashlib
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.types import ToolAnnotations

from atmem.agent_team.client import TeamClient, tool_functions


def register(mcp, settings, repository):
    root = settings.home / "team-bindings"
    if not root.is_dir() or root.is_symlink():
        return

    def call(operation, arguments):
        token = get_access_token()
        needed = "memory:read" if operation in {"inbox", "review"} else "memory:write"
        if (
            not token
            or not token.subject
            or needed not in token.scopes
            or "memory:read" not in token.scopes
        ):
            return {"ok": False, "code": "permission_rejected"}
        try:
            if not repository.claim_account_request(token.subject):
                return {"ok": False, "code": "account_rate_limited"}
            filename = hashlib.sha256(token.subject.encode()).hexdigest() + ".json"
            client = TeamClient.from_file(root / filename, "chatgpt", account=token.subject)
            result = client.call(operation, arguments)
            return {"ok": True, "data": result}
        except (PermissionError, FileNotFoundError):
            return {"ok": False, "code": "team_binding_unavailable"}
        except ValueError:
            return {"ok": False, "code": "invalid_handoff"}
        except Exception:
            return {"ok": False, "code": "team_service_unavailable"}

    for fn in tool_functions(call):
        read = fn.__name__ in {"team_inbox", "team_review"}
        scopes = ["memory:read"] if read else ["memory:read", "memory:write"]
        mcp.tool(
            annotations=ToolAnnotations(
                readOnlyHint=read, destructiveHint=False, idempotentHint=True, openWorldHint=False
            ),
            meta={"securitySchemes": [{"type": "oauth2", "scopes": scopes}]},
        )(fn)
