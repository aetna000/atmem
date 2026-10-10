AtMem 2.3.8 technical manuscript package
======================================

Contents
  atmem-2.3.8.tex       Main LaTeX manuscript
  atmem-2.3.8.pdf       PDF compiled from that exact source
  references.bib       Bibliography with primary-source links
  figures/            Four original figures, vector PDF and shareable PNG
  x-article.txt        Short X Article draft (plain text)
  x-post.txt           Launch post draft, under 280 characters
  huggingface-article.txt  Short Hugging Face article draft (plain text)
  build_figures.py     Figure and paired-count sensitivity calculations
  derived-statistics.json  Exact McNemar overlap sensitivity outputs
  evidence/           Compact reports and code exported from the stable source
  evidence-inventory.json  Per-file revision and SHA-256
  snapshot_evidence.py Evidence export and displayed-count checks
  requirements.txt    Pinned Python dependencies used for figure generation
  package_artifacts.py  Rebuild source and complete-package ZIP files

Build
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/python build_figures.py
  tectonic --keep-intermediates atmem-2.3.8.tex
  .venv/bin/python package_artifacts.py

Alternative standard TeX build
  pdflatex atmem-2.3.8.tex
  bibtex atmem-2.3.8
  pdflatex atmem-2.3.8.tex
  pdflatex atmem-2.3.8.tex

No nonstandard conference template is required. Do not upload the full evidence
directory as arXiv TeX input; the separate source ZIP contains the manuscript,
bibliography, PDF figures and build instructions.

Evidence and claim boundaries
  Architecture: stable v2.3.8, commit 267c5b3, compared with v2.3.7 cb1cf0f.
  Utility: historical candidate artifacts, including 2.3.8b6; not all measured
  on the stable release commit. The final Dolphin candidate is b97d35e.
  Integrity: installed 2.3.8 wheel at fdc63de using unchanged AGMI 0.6.3.
  The manuscript is a technical preprint draft, not peer reviewed or submitted.
  No new benchmark runs or paid model calls were made for this manuscript.
  The external raw benchmark volume was unavailable; compact results and
  implementation were inspected. Raw trajectories were not independently
  regraded. Source hashes identify artifacts, not correctness proofs.
  Mem0 uses infer=False with hash embeddings. AgentRunbook-R uses the local
  hash embedding route. These are not strongest-configuration comparisons.
  No broad superiority or significant benchmark win is claimed.
  Theorems are conditional architecture statements, not verified code proofs.

Before submission, the author should confirm authorship details, audit raw
artifact identities and paired case outcomes, and review the disclosed
configuration, lifecycle-integrity and development-adaptation limitations.
The article drafts are supplied for editing and have not been published.
