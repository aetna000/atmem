"""Serve scoped MCP tools or provision a dedicated host credential."""

import argparse
from getpass import getpass
import json
import os
from pathlib import Path

from .client import TeamClient, address, tool_functions
from .portable import HOSTS, host_identity


def grant(args):
    from atmem.control.manager import ControlPlaneManager
    from atmem.evidence import EvidenceRole, EvidenceScope
    from atmem.agent_team.portable import resolve_host
    from atmem.evidence import EvidencePrincipal

    address(args.endpoint)
    name = "team:" + args.host + ":" + args.agent
    host_identity(name)
    manager = ControlPlaneManager(state_path=args.state)
    identity = manager.identity_service()
    login = identity.login(args.username, getpass("AtMem password: "), source="local-team-cli")
    try:
        if login["account"].get("password_change_required"):
            raise PermissionError("Change the temporary account password first.")
        owner = identity.evidence_principal(login)
        scope = EvidenceScope(owner.scope.tenant_id, owner.scope.subject_id, args.workspace)
        resolve_host(manager, EvidencePrincipal(name, EvidenceRole.TEAM_HOST, scope))
        path = Path(args.binding).expanduser()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        service = manager.evidence_service()
        granted = False
        try:
            with os.fdopen(fd, "w") as handle:
                data = service.grant(owner, principal_id=name, role=EvidenceRole.TEAM_HOST, scope=scope)
                granted = True
                data.update(format="atmem-team-binding-v1", endpoint=args.endpoint)
                if args.account:
                    data["account"] = args.account
                json.dump(data, handle)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            if granted:
                service.revoke(owner, principal_id=name)
            path.unlink(missing_ok=True)
            raise
        print(f"Saved binding for {name} to {path}.")
    finally:
        identity.logout(login["session_token"])


def main():
    from atmem.control.manager import DEFAULT_STATE_PATH

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("grant", "serve"):
        child = sub.add_parser(action)
        child.add_argument("--binding", required=True)
        child.add_argument("--host", choices=HOSTS, required=True)
        if action == "grant":
            child.add_argument("--agent", required=True)
            child.add_argument("--workspace", required=True)
            child.add_argument("--username", required=True)
            child.add_argument("--endpoint", required=True)
            child.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
            child.add_argument("--account", help="ChatGPT OAuth subject for an account-specific binding")
    args = parser.parse_args()
    if args.action == "grant":
        grant(args)
        return
    from mcp.server.fastmcp import FastMCP

    client = TeamClient.from_file(args.binding, args.host)
    mcp = FastMCP("AtMem team")
    for fn in tool_functions(client.call):
        mcp.tool()(fn)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
