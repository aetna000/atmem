"""Rich extractor input coverage, separate from the limited syntax fallback.

These are eligible inputs, not claims that every framework/edge is resolved.
Ignore, secret, source-size and isolated-provider policies still apply.
"""
from pathlib import PurePosixPath

from atmem.code.graph import _TEXT_EXTENSIONS

SOURCE_POLICY = "source-only-v4-pinned-enola-language-manifests"
SOURCE_EXTENSIONS = frozenset(_TEXT_EXTENSIONS | {
    ".pyi", ".mjs", ".cjs", ".mts", ".cts", ".cc", ".cxx", ".c++", ".hh", ".hpp", ".hxx",
    ".kt", ".kts", ".php", ".phtml", ".scala", ".sc", ".dart", ".proto", ".tf", ".tfvars", ".hcl",
    ".csproj", ".fsproj", ".vbproj", ".sln", ".props", ".targets", ".xml", ".gradle",
    ".mod", ".sum", ".lock", ".gemspec", ".sql", ".rst", ".mdx",
    ".h++", ".inl", ".ipp", ".tpp", ".gts", ".gjs", ".hbs", ".graphql", ".gql",
    ".vue", ".svelte", ".php4", ".php5", ".php7", ".phps", ".prisma", ".config", ".sbt", ".nuspec", ".cmake",
})
SOURCE_NAMES = frozenset({"Gemfile", "Rakefile", "Dockerfile", "Containerfile", "Makefile",
    "CMakeLists.txt", "Pipfile", "Brewfile", "Package.swift", "Podfile", "WORKSPACE", "BUILD"})


def eligible_source(name):
    path = PurePosixPath(name)
    return path.suffix.lower() in SOURCE_EXTENSIONS or path.name in SOURCE_NAMES
