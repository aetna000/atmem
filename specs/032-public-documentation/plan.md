# Implementation plan

Use public docs/website/manifest.json as the editorial routing and release inventory;
reuse existing detailed guides through explicit mappings rather than copy their prose.
Add concise journey landing pages and an executable offline quickstart.
Private Astro renders sanitized Markdown through a shared-token docs layout with
section navigation, local client-side search, heading links and copy enhancement.
Keep existing marketing pages zero-JS; documentation enhancements are first-party and
not needed for content/navigation (constitution VI already permits this).

Private docs-source.json pins the public SHA. A standalone importer reads Git blobs
without executing public code, validates paths and revision provenance, and emits
ignored normalized content. Development override is explicit. CI fetches the public
repository and uses the pin; production verifies ancestry in public main.
Markdown links to mapped pages become site routes; other repository links point at
the immutable GitHub revision. Do not fetch remote images or embed external media.

Public validation checks inventory/version/source files and executable quickstart.
Private tests cover injection/path traversal, rendered links, layout and no-JS.
GitHub PR workflow builds/tests without secrets. Main-only production workflow requires
a protected production environment and Firebase identity; no deployment on PR events.
Document protection setup, sync/update procedure and recovery. Public release gate
requires documentation inventory to match the package release version.

Claude CLI reviews this proposal read-only before implementation; incorporate reasonable
feedback and re-review. Existing private Spec 003 remains broader planned work.
Keep public author aetna000 <aetna000@gmail.com> and private author
Javad Taghia <javad@deegitals.com>. No change to user work outside this scope.

Review refinements: build/render jobs have no deployment secrets. Deploy only their
validated artifact in a separate protected main-only job. Never merge one repository
into the other. Use latest-only documentation URLs and keep historic release pages;
retain routes on updates. Limit imports to 150 pages, 512 KiB each and 16 MiB total;
reject symlinks, non-NFC names, case collisions and unsafe URL schemes. Sanitize
rendered HTML in addition to disabling raw HTML. No remote media embedding.
Search is a small local JSON index; section indexes work without JS. Inject copy
buttons only after JS loads. Version validation derives expected version from
pyproject.toml. Run installed-wheel quickstart independently of working-tree imports.
