"""Deterministic, validation-safe projections of structured host state."""

from __future__ import annotations

import re
from typing import Any


_A11Y_CONTROL = re.compile(
    r"\b(textbox|searchbox|combobox|checkbox|radio|option|tab|spinbutton|slider)"
    r"\s+'([^'\n]{0,512})'([^\n]*)",
    re.I,
)
_A11Y_ATTRIBUTE = re.compile(
    r"\b(value|checked|selected|disabled|expanded|pressed)="
    r"(?:'([^']*)'|\"([^\"]*)\"|([^,\s]+))",
    re.I,
)
_A11Y_SURFACE = re.compile(
    r"\b(RootWebArea|button|link|textbox|searchbox|combobox|listbox|checkbox|"
    r"radio|menuitem|tab|spinbutton|slider|option|heading)"
    r"\s+'([^'\n]{0,512})'",
    re.I,
)
_ICON_PREFIX = re.compile(r"^(?:\\u[0-9a-fA-F]{4}|[\ue000-\uf8ff])\s*")


def structured_control_index(source: dict[str, Any]) -> str:
    """Return a compact, reproducible index of observable UI control state.

    The original accessibility tree remains the authority. Both formation and
    validation call this function, so a projection is admitted only when it
    can be reproduced exactly from that immutable source.
    """
    lines: list[str] = []
    seen: set[str] = set()
    for field in ("accessibility_tree", "tree"):
        value = source.get(field)
        if not isinstance(value, str):
            continue
        for role, raw_label, tail in _A11Y_CONTROL.findall(value):
            label = " ".join(raw_label.split())
            if not label:
                continue
            attributes: list[str] = []
            for name, single, double, bare in _A11Y_ATTRIBUTE.findall(tail):
                observed = single if single != "" else double if double != "" else bare
                if name.casefold() == "value" and observed == "":
                    observed = "<blank>"
                attributes.append(f"{name.casefold()}='{observed}'")
            role_name = role.casefold()
            # An open select can expose hundreds of unselected options. Their
            # exact labels and order remain losslessly available in the raw
            # accessibility source; duplicating every false option into the
            # state index adds storage and retrieval noise without describing
            # the control's current state. Retain selected or disabled options.
            if role_name == "option" and not any(
                attribute.casefold() in {"selected='true'", "disabled='true'"}
                for attribute in attributes
            ):
                continue
            if not attributes and role.casefold() in {"textbox", "searchbox"}:
                attributes.append("value='<blank>'")
            if not attributes:
                continue
            rendered = f"{role_name} '{label}' " + " ".join(attributes)
            identity = rendered.casefold()
            if identity in seen:
                continue
            seen.add(identity)
            lines.append(rendered)
    return "\n".join(lines)


def structured_surface_index(source: dict[str, Any]) -> str:
    """Return ordered, retrieval-ready labels for a complete UI surface.

    Raw accessibility trees remain authoritative and lossless. This projection
    preserves the closed set and source order of actionable/structural labels
    without duplicating generic containers and repeated static text. It lets a
    reader distinguish an absent option from a relevant snapshot that merely
    happened to be split across storage chunks.
    """
    lines: list[str] = []
    previous = ""
    for field in ("accessibility_tree", "tree"):
        value = source.get(field)
        if not isinstance(value, str):
            continue
        for role, raw_label in _A11Y_SURFACE.findall(value):
            label = _ICON_PREFIX.sub("", " ".join(raw_label.split()))
            if not label:
                continue
            rendered = f"{role.casefold()} '{label}'"
            if rendered.casefold() == previous:
                continue
            lines.append(rendered)
            previous = rendered.casefold()
    return "\n".join(lines)
