from benchmarks.code_replay.corrective_trace_audit import source_text_overlap


def test_overlap_is_distinct_nontrivial_text_not_token_or_attention_claim():
    line = '    return user_configuration.current_revision'
    pack = '[AtMem structure example.py:1-3]\n1: def f():\n2: '+line+'\n3: [docstring omitted; source available at this location]'
    event = {'type': 'item.completed', 'item': {'id': 'read', 'type': 'command_execution',
                                               'aggregated_output': '2: '+line+'\n'+line}}
    value = source_text_overlap(pack, [event, event])
    assert value['eligible_distinct_pack_lines'] == value['matching_distinct_lines'] == 1
    assert value['commands_with_matching_text'] == 1
    assert value['matching_distinct_utf8_bytes'] == len(line.encode())
    assert 'not proof' in value['assurance']
    assert source_text_overlap('', [event])['matching_distinct_lines'] == 0


def test_whitespace_and_unrelated_outputs_do_not_imply_overlap():
    line = 'return user_configuration.current_revision'
    event = {'type': 'item.completed', 'item': {'id': 'read', 'type': 'command_execution',
                                              'aggregated_output': '    '+line}}
    assert source_text_overlap('5: '+line, [event])['matching_distinct_lines'] == 0
