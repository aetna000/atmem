# Publishing the AtBot companion

AtBot's PyPI distribution is **`atmem-atbot`**. It installs the Python import
package and command named **`atbot`**. The distribution name is intentionally
different because the `atbot` project name on PyPI belongs to an unrelated
project.

AtMem pins the exact companion version. Publish the matching AtBot version
before publishing an AtMem release that requires it.

## One-time PyPI setup

Create a pending trusted publisher for a new PyPI project with these exact
values:

| Field | Value |
| --- | --- |
| PyPI project name | `atmem-atbot` |
| GitHub owner | `aetna000` |
| GitHub repository | `atmem` |
| Workflow filename | `publish-atbot.yml` |
| Environment name | `pypi-atbot` |

In the GitHub repository, create the `pypi-atbot` deployment environment and
protect it with required reviewers. No long-lived PyPI API token is needed or
stored in GitHub.

## Release

1. Update `packages/atbot/pyproject.toml` and AtMem's exact dependency together.
2. Run both Python suites and build both distributions locally.
3. Push the reviewed changes.
4. Create and push a tag matching `atbot-v<VERSION>`, for example
   `atbot-v0.1.0a6`.
5. Approve the protected `pypi-atbot` environment deployment.
6. Confirm `python -m pip install atmem-atbot==<VERSION>` installs an `atbot`
   command with the same version.

The workflow rejects a tag that does not exactly match the version in
`packages/atbot/pyproject.toml`, tests the companion, validates its wheel and
source distribution, and publishes through PyPI's short-lived OIDC identity.
