from pathlib import Path

from atmem.service import APIError, APIPrincipal


def test_agent_admin_operation_matrix_and_openapi_resources() -> None:
    agent = APIPrincipal("a", "agent", "subject")
    admin = APIPrincipal("b", "admin", "subject")
    for operation in ("audit:read", "config:write", "memory:delete", "migration:run"):
        try:
            agent.require(operation)
        except APIError as exc:
            assert exc.status == 403
        else:
            raise AssertionError(operation)
        admin.require(operation)
    contract = (Path(__file__).parents[1] / "docs/contracts/atmem-api-v1.openapi.yaml").read_text()
    for resource in ("/health:", "/capabilities:", "/memories:", "/query:", "/reviews:", "/audit:", "/configuration:"):
        assert resource in contract


def test_scope_identity_changes_cursor_binding() -> None:
    first = APIPrincipal("a", "agent", "one")
    second = APIPrincipal("a", "agent", "two")
    assert first.scope_sha256 != second.scope_sha256
