"""Server cache policy expressed only through the public cache interface."""
def invalidate_scope(cache, *, tenant_id: str, workspace_id: str) -> None:
    # Retrieval keys are already authority-scoped; tenant isolation happens in
    # the repository and each tenant owns a cache instance.
    del tenant_id
    cache.invalidate(workspace_id=workspace_id)
