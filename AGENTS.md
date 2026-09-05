# Repository instructions for coding agents

## Release completion rule

A request to **prepare** a release authorizes version and documentation changes
only. A request to **create**, **publish**, or **make** a release is not complete
after pushing a branch or changing `pyproject.toml`.

For every release created by an agent:

1. Set one explicit release version in every package and installer constant
   that participates in the release. Keep the AtMem, AtBot, and OpenClaw bridge
   compatibility pins aligned.
2. Add `docs/releases/v<VERSION>.md` before tagging. The note must explain the
   user-visible change, exact install/upgrade commands, migration or opt-in
   behavior, compatibility, and honest limitations.
3. Run the applicable Python, companion, OpenClaw, build, metadata, and
   installed-artifact gates. Do not tag a failing or dirty commit.
4. Commit and push the release changes before creating tags.
5. When AtBot changes, create and push the annotated
   `atbot-v<ATBOT_VERSION>` tag first. Wait for `publish-atmem-atbot` to succeed
   and verify the companion version exists on PyPI.
6. Create the annotated `v<VERSION>` tag on the exact reviewed commit and push
   it. Never move or overwrite a published tag.
7. Wait for the `publish` workflow to finish. Verify the GitHub prerelease,
   AtMem PyPI version, and matching OpenClaw npm bridge rather than assuming a
   pushed tag produced them.
8. Report the branch, commit, tags, workflow result, release URL, and package
   versions. Clearly distinguish “release candidate pushed” from “release
   published.”

If credentials, protected-environment approval, or a failed external workflow
prevents completion, stop and report that exact blocker. Do not claim the
release exists merely because its source commit is in the repository.
