"""Redacted service health and metrics."""
def health(*, authenticated: bool, dependencies: dict[str, str]):
    if not authenticated: raise PermissionError("health authentication required")
    return {"status": "ok" if all(v == "ok" for v in dependencies.values()) else "degraded", "dependencies": dict(dependencies)}
def metrics(rows):
    return {"requests": len(rows), "failures": sum(not bool(r.get("success", True)) for r in rows)}
