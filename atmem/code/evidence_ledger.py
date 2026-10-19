"""Ephemeral delivery knowledge, never an assertion about model attention."""
from collections import OrderedDict


class EvidenceLedger:
    def __init__(self, *, sessions=64, entries=256):
        self.sessions, self.entries = sessions, entries
        self._delivered = OrderedDict()

    def delivered(self, session, epoch, items):
        key = (session, epoch)
        values = self._delivered.setdefault(key, OrderedDict())
        self._delivered.move_to_end(key)
        for item in items:
            if item.get('status') in {'missing', 'withheld', 'reference'}:
                continue
            values[item['id']] = item['version']
            values.move_to_end(item['id'])
        while len(values) > self.entries:
            values.popitem(last=False)
        while len(self._delivered) > self.sessions:
            self._delivered.popitem(last=False)

    def has(self, session, epoch, identity, version):
        return self._delivered.get((session, epoch), {}).get(identity) == version
