# Coordinated AtFlows, AtMem, and AtMem.ai releases

The release lead owns the end-to-end checklist and reports each publication
state truthfully. AtFlows and AtMem are public GitHub/PyPI releases; AtMem also
publishes the matching OpenClaw npm bridge. AtMem.ai is a separate private
website repository and Firebase Hosting deployment. A package release does not
make the website current, and a merged website PR is not a deployment.

## 1. Freeze the release contract

- Name the intended AtFlows, AtMem, AtBot (if changed), and OpenClaw bridge
  versions. Decide whether each is stable or prerelease. Align exact dependency
  pins, installer constants, status output, examples, and compatibility text.
- Inspect both repositories' working trees, open PRs, tags, and published
  versions. Never move an existing tag or silently overwrite an artifact.
- Write a capability/coverage matrix from shipped code and tests: installation,
  upgrade and migration, CLI/status, AtBot, AtFlows, OpenClaw and other supported
  adapters, memory and retrieval, evidence/multimodal, security/privacy, UI,
  limitations and opt-ins. Review only affected rows in depth, but check every
  public guide for contradictory versions or capability claims.
- Put exact install/upgrade commands, compatibility, defaults/opt-ins, migration,
  user-visible changes, and honest limitations in each changed package's release
  note. Keep AtMem's `docs/website/manifest.json`, imported guides, reference,
  examples, and release index in sync. AtFlows' user guide and release note must
  describe its standalone and AtMem-managed modes accurately.

## 2. Publish AtFlows first when its version changes

Follow the AtFlows repository's `docs/releasing.md`. Review and merge its PR,
run its tests, typecheck, build, package/metadata and clean-install gates, then
tag the exact reviewed `main` commit. Publish its wheel and source distribution
to PyPI using the repository's ignored local `.env` `PYPI_TOKEN` only when the
normal publisher does not handle this. Never print or commit credentials. Verify
the GitHub release, PyPI files, clean `pip install atflows==<VERSION>`, CLI
version, and dependency health. Do not merge AtMem's new exact AtFlows pin until
that PyPI version is actually installable.

## 3. Publish AtMem

Follow this repository's `AGENTS.md` release rule. Review and merge the public
PR, run the Python/AtBot/OpenClaw/documentation/build/metadata/installed-artifact
gates, and tag only the exact reviewed commit. If AtBot changed, publish and
verify its annotated tag and PyPI distribution before AtMem. Wait for AtMem's
release workflow and verify the GitHub release, AtMem wheel/sdist on PyPI,
fresh-install and persisted-upgrade smoke tests, CLI version, and matching
OpenClaw npm bridge. Registry metadata appearing before a normal clean install
is not sufficient: retry after index propagation or inspect the published
artifact, and report any remaining installability gap.

## 4. Prepare the AtMem.ai documentation PR

In `/Users/javadtaghia/gitlab/atmemai-platform`, use the repository's existing
`javadtaghia` SSH remote and Git author. The public AtMem Markdown manifest is
the editorial source; the private site imports allowlisted docs as data only.
After the public release commit is on AtMem `main`, pin its immutable SHA in
`docs-source.json`, update `site/src/data/release.json`, review the claim
registry, import docs and update the content lock. Cover AtMem and AtFlows
getting started, managed versus standalone use, integrations, reference,
examples, troubleshooting, release notes and known limits. Check navigation,
search, internal links, displayed versions, install commands and the source SHA.
Run the private repo's build, gates, docs tests and browser checks; open a PR
against private `main` for the owner to review. Do not self-merge or deploy a
feature branch. See its `docs/documentation-publishing.md`.

## 5. Deploy the owner-merged website

Only after the owner merges the private PR and explicitly requests publication,
confirm the successful `website / validate` run belongs to that exact private
`main` SHA. Download its `validated-website` artifact, verify
`website.tar.gz.sha256`, extract it, then run Firebase CLI **from the extracted
artifact directory**:

```bash
firebase deploy --only hosting --project atmemai --non-interactive -m "Validated main MAIN_SHA"
```

Never deploy a local rebuild or Firestore rules as part of this step. Verify the
live custom domain and Firebase Hosting domain: homepage, `/docs/`, search,
getting started, relevant AtFlows and AtMem guides, release notes, links,
displayed versions and immutable docs source SHA. Compare representative live
files to the validated artifact, and record the main SHA, validation run,
checksum, CLI result, and live checks.

## Handoff report

Report AtFlows and AtMem branches/commits/tags, tests, GitHub releases, PyPI
versions, npm bridge version, and clean-install results. Separately report the
private website PR, owner merge, validation run, Firebase deployment and live
URLs. Explicitly label any pending owner review, credential/approval blocker,
failed check, or registry propagation. Never call the coordinated rollout fully
published while a required website update is still only a PR.
