"""Discovery qualifications are not inherited from capture-hook support."""
from dataclasses import dataclass

HOSTS = ('claude', 'codex', 'copilot', 'muse', 'grok')
PLATFORMS = ('Darwin', 'Windows', 'Linux')
LEVELS = ('unprobed', 'optional_discovery', 'routed_discovery', 'unavailable')


@dataclass(frozen=True)
class DiscoveryHost:
    host: str
    platform: str
    version: str = 'unverified'
    capability: str = 'unprobed'
    boundary: str = 'not_qualified'
    receipt_id: str | None = None

    def __post_init__(self):
        if self.host not in HOSTS or self.platform not in PLATFORMS or self.capability not in LEVELS:
            raise ValueError('invalid discovery host cell')
        if not isinstance(self.version, str) or not self.version or len(self.version) > 200:
            raise ValueError('invalid host version')
        # Receipts are locators, not proof: real authorization/probe verification
        # must occur in the eventual host qualification service before promotion.
        if self.capability in {'optional_discovery', 'routed_discovery'}:
            raise ValueError('qualified capabilities require a verified host probe service')
        if self.receipt_id is not None:
            raise ValueError('unqualified inventory cannot assert a probe receipt')


def unprobed_matrix():
    return tuple(DiscoveryHost(host, platform) for host in HOSTS for platform in PLATFORMS)
