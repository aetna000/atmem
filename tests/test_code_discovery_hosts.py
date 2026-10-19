import pytest

from atmem.code.discovery_hosts import DiscoveryHost, unprobed_matrix


def test_all_five_hosts_have_separate_os_cells_without_inherited_claims():
    matrix = unprobed_matrix()
    assert len(matrix) == 15
    assert len({(c.host, c.platform) for c in matrix}) == 15
    assert all(c.capability == 'unprobed' and c.receipt_id is None for c in matrix)


@pytest.mark.parametrize('values', [
    {'host': 'unknown'}, {'platform': 'unknown'}, {'capability': 'automatic'},
    {'capability': 'routed_discovery', 'receipt_id': 'fake'},
    {'capability': 'optional_discovery', 'receipt_id': 'fake'},
    {'version': ''}, {'receipt_id': 'unverified'}])
def test_inventory_cannot_self_certify_routing(values):
    with pytest.raises(ValueError):
        DiscoveryHost(**{'host': 'claude', 'platform': 'Darwin', **values})


def test_inventory_only_uses_read_only_commands_and_never_promotes():
    import base64
    from tools.qualify_discovery_hosts import inventory
    seen = []
    def probe(argv):
        seen.append(argv)
        return {'stdout_base64': base64.b64encode(b'fixture --tools --mcp-config').decode()}
    rows = inventory(probe=probe, which=lambda host: '/fixture/' + host)
    assert len(rows) == 5 and len(seen) == 10
    assert all(argv[1] in {'--version', '--help'} for argv in seen)
    assert all(row['capability'] == 'unprobed' for row in rows)


def test_missing_binary_is_explicit_without_dispatch():
    from tools.qualify_discovery_hosts import inventory
    rows = inventory(probe=lambda argv: pytest.fail('missing binary dispatched'), which=lambda host: None)
    assert all(row['capability'] == 'unavailable' for row in rows)
