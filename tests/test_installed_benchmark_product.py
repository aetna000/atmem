from __future__ import annotations

from pathlib import Path
import pytest


class _Distribution:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.files = (Path("atmem/__init__.py"), Path("atmem-2.3.8b6.dist-info/METADATA"))

    def locate_file(self, entry: str | Path) -> Path:
        return self.root / Path(entry)


def test_installed_identity_rejects_checkout_import(tmp_path: Path, monkeypatch) -> None:
    from research.production_benchmarks import installed_product

    package = tmp_path / "site-packages/atmem/__init__.py"
    metadata = tmp_path / "site-packages/atmem-2.3.8b6.dist-info/METADATA"
    package.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    package.write_text("", encoding="utf-8")
    metadata.write_text("Version: 2.3.8b6\n", encoding="utf-8")
    monkeypatch.setattr(installed_product, "distribution", lambda _name: _Distribution(tmp_path / "site-packages"))
    monkeypatch.setattr(installed_product, "version", lambda _name: "2.3.8b6")

    with pytest.raises(RuntimeError, match="checkout instead of the installed"):
        installed_product.installed_atmem_identity("2.3.8b6")


def test_installed_identity_hashes_the_imported_distribution(
    tmp_path: Path, monkeypatch
) -> None:
    import atmem
    from research.production_benchmarks import installed_product

    root = tmp_path / "site-packages"
    package = root / "atmem/__init__.py"
    metadata = root / "atmem-2.3.8b6.dist-info/METADATA"
    package.parent.mkdir(parents=True)
    metadata.parent.mkdir(parents=True)
    package.write_text("installed", encoding="utf-8")
    metadata.write_text("Version: 2.3.8b6\n", encoding="utf-8")
    monkeypatch.setattr(atmem, "__file__", str(package))
    monkeypatch.setattr(installed_product, "distribution", lambda _name: _Distribution(root))
    monkeypatch.setattr(installed_product, "version", lambda _name: "2.3.8b6")

    result = installed_product.installed_atmem_identity("2.3.8b6")

    assert result["module"] == str(package.resolve())
    assert result["artifact_sha256"].startswith("sha256:")
