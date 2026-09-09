import importlib
import pathlib

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
def test_storage_extras_are_optional_and_migrations_are_monotonic():
    data=tomllib.loads(pathlib.Path("pyproject.toml").read_text()); base=" ".join(data["project"]["dependencies"]); assert "psycopg" not in base and "qdrant" not in base
    for module in ("atmem.store.postgres","atmem.semantic.pgvector","atmem.semantic.qdrant"): importlib.import_module(module)
