"""Package the reviewed manuscript; exclude transient TeX build files."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
source_files = [ROOT / name for name in (
    "atmem-2.3.8.tex", "atmem-2.3.8.bbl", "references.bib", "README.txt"
)] + sorted((ROOT / "figures").glob("*.pdf"))
atmem_only_source_files = [ROOT / name for name in (
    "atmem-2.3.8-atmem-only.tex", "atmem-2.3.8-atmem-only.bbl", "references.bib"
)] + [ROOT / "figures" / name for name in (
    "architecture.pdf", "evidence_flow.pdf", "integrity.pdf"
)]
all_files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and p.suffix not in {".zip", ".aux", ".log", ".out", ".blg", ".pyc"}
                   and "claude-review" not in p.relative_to(ROOT).parts
                   and p.name != "delivery-manifest.json")

for name, paths in (("atmem-2.3.8-latex-source.zip", source_files),
                    ("atmem-2.3.8-atmem-only-source.zip", atmem_only_source_files),
                    ("atmem-2.3.8-complete-package.zip", all_files)):
    with zipfile.ZipFile(ROOT / name, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT))
    with zipfile.ZipFile(ROOT / name) as archive:
        assert archive.testzip() is None

# Minimal arXiv upload: one obvious top-level source, a matching processed
# bibliography, the BibTeX database, and only the figures used by the paper.
arxiv_files = [
    (ROOT / "atmem-2.3.8.tex", "main.tex"),
    (ROOT / "atmem-2.3.8.bbl", "main.bbl"),
    (ROOT / "references.bib", "references.bib"),
] + [(path, str(path.relative_to(ROOT)))
     for path in sorted((ROOT / "figures").glob("*.pdf"))]
arxiv_name = "atmem-2.3.8-arxiv-source.zip"
with zipfile.ZipFile(ROOT / arxiv_name, "w", zipfile.ZIP_DEFLATED) as archive:
    for path, archive_name in arxiv_files:
        archive.write(path, archive_name)
with zipfile.ZipFile(ROOT / arxiv_name) as archive:
    assert archive.testzip() is None

manifest = {p.name: {"bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(ROOT.iterdir()) if p.is_file()
            and p.suffix in {".tex", ".pdf", ".zip", ".txt"}}
(ROOT / "delivery-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({name: details["bytes"] for name, details in manifest.items()}, indent=2))
