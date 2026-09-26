"""Versioned directory-plugin payload supplied by an installed AtMem wheel."""
from importlib.metadata import version
from importlib.resources import files


def plugin_files() -> dict[str, bytes]:
    root = files("atmem.adapters.hermes")
    return {
        "__init__.py": root.joinpath("assets/plugin_entry.py").read_bytes(),
        "provider.py": root.joinpath("provider.py").read_bytes(),
        "client.py": root.joinpath("client.py").read_bytes(),
        "plugin.yaml": (
            f"name: atmem\nversion: {version('atmem')}\n"
            "kind: exclusive\nrequires_hermes: '==0.21.5'\n"
            "description: 'AtMem local CLI preview. Scoped connection required; inspect atmem hermes status before activation.'\n"
        ).encode(),
    }
