"""Host-neutral dashboard for governed memory and agent-flight evidence.

The dashboard has no external assets or JavaScript dependencies. It presents
the customer decisions that matter: inspect evidence, review memory, activate
AtMem, or return safely to the adapter's prior state.

The served page is assembled from three package assets so markup, styling,
and behavior can be edited as ordinary files while the HTTP surface keeps
serving one self-contained document:

    assets/app.html   page shell and markup
    assets/app.css    stylesheet, inlined at the CSS token
    assets/app.js     application script, inlined at the JS token
"""

from importlib.resources import files

_STYLE_TOKEN = "/*==ATMEM_INLINE_CSS==*/\n"
_SCRIPT_TOKEN = "/*==ATMEM_INLINE_JS==*/\n"


def _asset(name: str) -> str:
    return (
        files("atmem.control").joinpath("assets", name).read_text(encoding="utf-8")
    )


def build_app_html() -> str:
    """Assemble the single served dashboard document from package assets."""
    shell = _asset("app.html")
    for token, name in ((_STYLE_TOKEN, "app.css"), (_SCRIPT_TOKEN, "app.js")):
        if token not in shell:
            raise ValueError(f"dashboard shell is missing {token.strip()!r}")
        shell = shell.replace(token, _asset(name), 1)
    return shell


APP_HTML = build_app_html()
