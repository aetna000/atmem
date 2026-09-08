import json,pathlib,tomllib
def test_sdk_is_dependency_free_apache_and_versioned():
    package=json.loads(pathlib.Path("packages/typescript/package.json").read_text()); assert package.get("license")=="Apache-2.0" and not package.get("dependencies")
    assert pathlib.Path("packages/typescript/LICENSE").is_file(); assert tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["license"]=="Apache-2.0"
