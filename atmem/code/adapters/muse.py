"""Muse project hook packaging; live context verification is required."""
from atmem.code.adapters.json_hooks import JsonHookAdapter


class MuseAdapter(JsonHookAdapter):
    host = "muse"
    relative_path = ".muse/hooks.json"
