"""Guard against presenting content omissions as demonstrated memory failures."""
import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[2] / 'scripts/export_dolphin_action_evidence.py'
spec = importlib.util.spec_from_file_location('action_evidence', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def action(reason, *, kind='judged', calls=(0,)):
    return {'passed':False,'call_indices':list(calls),'checks':[{'kind':kind,'call_evaluations':[{'ok':False,'reason':reason}]}]}


def test_missing_content_does_not_establish_memory_delivery():
    label, basis = module.classification(action('The message omits the required manual review rule.'))
    assert label == 'missing_required_fact'
    assert label != 'missing_remembered_fact'
    assert 'assessed separately' in basis


def test_absent_call_takes_precedence_over_content_diagnosis():
    assert module.classification(action('Wrong recipient', calls=()))[0] == 'no_call'


def test_mechanical_error_is_wrong_value_even_with_missing_prose():
    assert module.classification(action('Missing expected recipient', kind='mechanical'))[0] == 'wrong_value'


def test_unspecific_reason_remains_unresolved():
    assert module.classification(action('Criterion not met.'))[0] == 'unresolved_content'


def test_nonprefix_read_tools_are_recognized():
    assert {'vector_search','query_experiment_results','metrics_fetch_batch'} <= module.READ_EXCEPTIONS
    assert not module.READ.match('send_email')


def test_source_delivery_can_be_decoded_from_nested_tool_text():
    import json
    content = {'content':[{'type':'text','text':json.dumps({'facts':[{'quote':'Source quoted fact','session':'001452'}]})}]}
    assert any(obj.get('quote') == 'Source quoted fact' for obj in module.embedded_objects(content))
