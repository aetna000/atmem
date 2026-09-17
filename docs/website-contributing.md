# Contribute to the official documentation

The official docs are rendered at `https://atmem.ai/docs/`. Their editorial
source lives here; the website renderer, hosting configuration and other routes
remain in a separate private repository.

## Make a documentation change

1. Find the page in `docs/website/manifest.json`, or use its website Edit link.
2. Edit that Markdown file. Reuse relative links to other source documents.
   Do not add executable MDX, scripts, raw HTML embeds or remote image trackers.
3. New pages need an explicit title/slug/source entry in the manifest and a
   link from their section. Keep published slugs stable.
4. State prerequisites, supported version, authority, side effects, expected
   results and cleanup for operational examples. Label synthetic data and any
   model/network requirements. Do not copy secrets or real session data.
5. Run `python scripts/check_website_docs.py` and
   `python -m pytest -q tests/test_website_docs.py`, then open a pull request.

The owner reviews and merges public changes. A separate reviewed source-pin PR
imports the immutable public-main revision into the private website. Only that
repository's main workflow publishes. Merging a public docs PR does not itself
mean the website has deployed it.

## Release hook

For each AtMem release, update manifest version and affected guides/examples,
add its release note and retain earlier release pages. Validate against the
package version and test the first-run sample against the installed artifact.
Request the private website pin/claim/version refresh and verify its published
revision afterward. Report a pending website deployment separately from package
publication. Do not claim new defaults or universal speed gains from a narrow
benchmark; preserve optional-feature and host-coverage labels.
