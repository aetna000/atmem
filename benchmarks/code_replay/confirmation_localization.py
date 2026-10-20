"""Unscored transfer selection; distinct from both familiar and retired tasks.

7c99ebe excluded before any solver dispatch: its edited report could not be
recovered before the solution cutoff. Original eligibility evidence retained.
"""
from benchmarks.code_replay.confirmation import main

DEFINITIONS = (
    ("c8da1fc", 3364, "Parse multi-value defaults supplied as strings",
     "For multi-value Click parameters, a string in default_map should be split into values rather than unpacked character by character. Respect the parameter type's string-splitting behavior, including environment-style type-specific separators, nargs and multiple values. Existing sequences, numeric conversion, ordinary defaults and explicit command-line arguments must keep working."),
    ("b03f211", 3363, "Preserve non-basic flag values without explicit UNPROCESSED",
     "When a flag_value is a non-basic Python object such as an Enum member or a class, preserve the supplied object rather than stringifying it when type is not explicitly supplied. Users should not need to set type=click.UNPROCESSED just to keep that object. Preserve basic bool/int/float/string behavior, explicit type overrides, defaults and ordinary flag selection."),
    ("0cd28d6", 3208, "Do not suggest a shadowed help alias in error hints",
     "click.UsageError help hints must suggest a working help option for the current command. If a configured help alias such as -h is used by a user-defined value-taking option, do not suggest it as help; use a still-available help alias instead. Preserve the command path, custom help aliases and ordinary error output, and handle cases where help is disabled or no valid alias remains."),
    ("b7cf069", 2935, "Complete nested subcommand options and arguments",
     "Shell completion for a command inside nested Click groups must resolve the selected subcommand rather than keep suggesting that subcommand's name. After selecting it, offer its argument completion values and its own options, including custom argument completion and option prefixes. Preserve top-level group suggestions and ordinary completion behavior."),
    ("3bb230d", 3434, "Remove spurious whitespace from usage formatting",
     "HelpFormatter.write_usage must not leave trailing whitespace on usage lines or a whitespace-only separator line after the usage section. Produce a genuinely empty separator line while preserving the command/argument text, indentation, wrapping, custom prefixes and existing normal help formatting."),
)

if __name__ == "__main__":
    main(definitions=DEFINITIONS, qualification_run="efficiency-p3confirm-qualification-v2",
         selection="five explicitly selected different Click changes; first-loop transfer tasks retired; not a random/latest-five or repository-disjoint sample")
