"""Evaluator-only task packaging; never imports or invokes a solver.

Requirements are curated from retained pre-solution reports. They are not the
accepted patch or the later PR description. Every exclusion is decided before
target execution, without considering whether a memory would help.
"""
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from benchmarks.code_replay.grade import tree_files


def digest_files(files):
    return sha256(json.dumps({n: sha256(b).hexdigest() for n, b in sorted(files.items())},
                             sort_keys=True, separators=(",", ":")).encode()).hexdigest()


TASKS = (
    {"short": "b67832c", "issue": 2819, "cutoff": "2026-07-07T13:40:56Z",
     "title": "Resolve collisions between user parameters and automatic help",
     "requirements": "A user argument or option whose internal name is help must parse its value normally while the automatic --help option still displays help. Respect custom help_option_names. A user-defined --help option must retain its ordinary value-taking behavior and replace the automatic help flag. Preserve existing non-colliding behavior. Do not require a particular private storage name."},
    {"short": "9c4dfda", "pull": 3728, "cutoff": "2026-07-31T11:02:01Z",
     "title": "Make help-option name ordering reproducible",
     "requirements": "Command.get_help_option_names currently uses an unordered set and causes non-reproducible generated documentation. Return deterministic help option names, preserving the configured declaration order while eliminating duplicates and removing names already claimed by user options, including both sides of boolean flags. Preserve ordinary help behavior."},
    {"short": "150d107", "issue": 3571, "cutoff": "2026-08-15T07:01:10Z",
     "title": "Show the final progressbar position after throttled updates",
     "requirements": "With click.progressbar(range(20), show_pos=True, update_min_steps=7), completion currently displays 14/20 rather than 20/20. Finish at the full position regardless of a minimum-update threshold that does not divide the length, or exceeds it. Cover iteration and explicit update use; preserve hidden, unknown-length and normal progress behavior."},
    {"short": "fc5c7f4", "issue": 3731, "cutoff": "2026-08-13T09:13:53Z",
     "title": "Preserve pager errors during temporary-file cleanup",
     "requirements": "On the Windows temporary-file pager path, an exception while paging can leave the file open when cleanup unlinks it. Windows then raises PermissionError and masks the original error. Ensure cleanup closes the temporary file before unlinking on both successful and exceptional exits, preserves the original failure, and does not leak resources. Keep normal paging and color behavior. The evaluator exercises Windows file-lifetime semantics on macOS; this is not a native Windows qualification."},
    {"short": "e1fd594", "issue": 2869, "cutoff": "2026-08-19T06:09:09Z",
     "title": "Accept pathlib paths in the editor filename argument",
     "requirements": "click.edit(filename=pathlib.Path(...)) should accept the filesystem path instead of failing because a PosixPath is not iterable. Preserve string filenames, existing iterable filename support, and the public return semantics. Support path-like filenames individually and in an iterable without changing existing editor behavior."},
)


HELP_TEST = b'''import click
import pytest

@pytest.mark.parametrize("kind", ["argument", "option", "custom"])
def test_reported_help_collision(runner, kind):
    names = ["--man"] if kind == "custom" else ["--help"]
    params = ([click.Argument(["help"])] if kind == "argument" else
              [click.Option(["--value", "man" if kind == "custom" else "help"])])
    cli = click.Command("cli", params=params, context_settings={"help_option_names": names},
                        callback=lambda **values: click.echo(next(iter(values.values()))))
    result = runner.invoke(cli, ["sample"] if kind == "argument" else ["--value", "sample"])
    assert result.exit_code == 0, result.output
    assert result.output == "sample\\n"
    result = runner.invoke(cli, [names[0]])
    assert result.exit_code == 0
    assert "Show this message and exit." in result.output

def test_user_help_option_remains_value_taking(runner):
    @click.command()
    @click.option("--help", default="default value")
    def cli(help):
        click.echo(help)
    assert runner.invoke(cli, []).output == "default value\\n"
    assert runner.invoke(cli, ["--help", "custom"]).output == "custom\\n"
'''


def grader_tree(checkout, task):
    parent = tree_files(checkout, task["parent_commit"])
    reference = tree_files(checkout, task["reference_commit"])
    tree = dict(parent)
    if task["short"] == "b67832c":
        # The upstream patch fixes a private name to _click_default_help and
        # adds unrelated warning policy. Neither is in the pre-existing report.
        # Test behavior, not that oracle implementation detail. The info-dict
        # fixture asserts the old private help name and is explicitly excluded.
        tree.pop("tests/test_info_dict.py", None)
        tree["tests/test_reported_help_collision.py"] = HELP_TEST
    else:
        changed = subprocess.check_output(["git", "-C", str(checkout), "diff", "--name-only",
                                            task["parent_commit"], task["reference_commit"]], text=True).splitlines()
        for name in changed:
            if name.startswith("tests/") and name.endswith(".py") and "/typing/" not in name:
                tree[name] = reference[name]
    return tree


def solution_tree(grader, sources):
    return {**{n: b for n, b in grader.items() if not n.startswith("src/")},
            **{n: b for n, b in sources.items() if n.startswith("src/")}}


def gh_json(route):
    return json.loads(subprocess.check_output(["gh", "api", route], timeout=30))


def recover_report(task):
    number = task.get("issue", task.get("pull"))
    route = f"repos/pallets/click/issues/{number}"
    report = gh_json(route)
    field = "issue" if "issue" in task else "pullRequest"
    query = ('query { repository(owner:"pallets",name:"click") { ' + field + '(number:' + str(number) +
             ') { lastEditedAt } } }')
    edited = json.loads(subprocess.check_output(["gh", "api", "graphql", "-f", "query=" + query], timeout=30))
    return {"route": route, "report": report,
            "last_edited_at": edited["data"]["repository"][field]["lastEditedAt"],
            "use": "curated_observable_requirements_only_no_solution_snippets"}
