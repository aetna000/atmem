from copy import deepcopy
import pytest
from atmem.knowledge._vendor import code_retriever as imported
from atmem.knowledge.code.normalization import _ACTIVE, shared_metadata_scope, normalize_shared
from atmem.knowledge.code.queries import graph_input
from tests.test_knowledge_queries import generation


OPERATIONS = [('query_facts', {}), ('explore', {'id': 'entry'}), ('traverse', {'start_id': 'entry'}),
              ('find_path', {'source_id': 'entry', 'target_id': 'storage'}),
              ('impact_analysis', {'target_id': 'storage'}), ('architecture', {}), ('delta', {}), ('insights', {})]


@pytest.mark.parametrize('operation,config', OPERATIONS)
def test_all_operations_keep_exact_results_and_do_not_alias_metadata(operation, config):
    data = generation()
    data['receipt'] = {'source': 'retained', 'nested': {'files': ['a.py', 'b.py'], 'enabled': True}, 'none': None}
    data['repository'] = {'id': 'repo', 'name': 'project', 'last_delta': {'added': [], 'removed': []}}
    data['property_variants']['entry'] = [{'nested': {'value': 1}, 'confidence': 0.8}]
    before = deepcopy(data)
    nodes, edges = graph_input(data)
    baseline = imported.CodeRetriever(operation=operation, **config).execute(nodes, edges)
    actual = imported.CodeRetriever(operation=operation, **config).execute(nodes, edges, shared_metadata=(data['receipt'],))
    assert actual == baseline and data == before and _ACTIVE.get() is None
    def mutate(item):
        if isinstance(item, dict):
            for value in list(item.values()):
                mutate(value)
            item['arbitrary_caller_mutation'] = True
        elif isinstance(item, list):
            for value in list(item):
                mutate(value)
            item.append('caller mutation')
    mutate(actual)
    assert data == before


def test_repeated_receipt_is_normalized_once_but_every_property_filter_remains(monkeypatch):
    data = generation(); receipt = {'marker': {'version': 1}, 'rows': list(range(100))}; data['receipt'] = receipt
    nodes, edges = graph_input(data)
    original = imported._normalize_value_uncached
    visits = []
    def track(value):
        if value is receipt:
            visits.append(True)
        return original(value)
    monkeypatch.setattr(imported, '_normalize_value_uncached', track)
    config = {'property': 'extraction_receipt.marker', 'property_value': {'version': 1}}
    old = imported.CodeRetriever(operation='query_facts', **config).execute(nodes, edges)
    assert len(visits) == len(data['objects'])
    visits.clear()
    actual = imported.CodeRetriever(operation='query_facts', **config).execute(nodes, edges, shared_metadata=(receipt,))
    assert len(visits) == 1 and actual == old and actual['total'] == len(data['objects'])
    receipt['marker']['version'] = 2
    changed = imported.CodeRetriever(operation='query_facts', **config).execute(nodes, edges, shared_metadata=(receipt,))
    assert changed['total'] == 0 and _ACTIVE.get() is None


def test_exception_nested_scopes_and_missing_none_root_do_not_leak_state():
    metadata = {'nested': [1]}
    with shared_metadata_scope((metadata,)):
        outer = _ACTIVE.get()
        assert normalize_shared(None, lambda value: value) is None
        assert outer['normalized'] == {}
        with pytest.raises(RuntimeError):
            with shared_metadata_scope((metadata,)):
                assert _ACTIVE.get() is not outer
                raise RuntimeError('constructor failed')
        assert _ACTIVE.get() is outer
    assert _ACTIVE.get() is None


def test_constructor_failure_clears_memo_before_next_scope(monkeypatch):
    original = imported._CodeGraphSnapshot
    def fail(*args):
        assert _ACTIVE.get() is not None
        raise ValueError('invalid snapshot')
    monkeypatch.setattr(imported, '_CodeGraphSnapshot', fail)
    with pytest.raises(ValueError, match='invalid snapshot'):
        imported.CodeRetriever().execute([], [], shared_metadata=({'scope': 'one'},))
    assert _ACTIVE.get() is None
    monkeypatch.setattr(imported, '_CodeGraphSnapshot', original)
    assert imported.CodeRetriever(operation='query_facts').execute([], [])['total'] == 0


def test_concurrent_construction_scopes_do_not_share_metadata():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def run(marker):
        receipt = {'scope': marker}
        with shared_metadata_scope((receipt,)):
            barrier.wait(timeout=5)
            result = normalize_shared(receipt, deepcopy)
            assert result == receipt and result is not receipt
            return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, ['subject-one', 'subject-two'])) == [{'scope': 'subject-one'}, {'scope': 'subject-two'}]
