from research.retrieval_2310.reference_host import reference_souls


def test_reference_host_identity_uses_registry_not_persona_id_or_fact_labels(tmp_path):
    (tmp_path/'harness').mkdir();(tmp_path/'registry').mkdir()
    (tmp_path/'harness/benchmark_soul.md').write_text('Assistant for {{persona_name}}. History is from that user.')
    (tmp_path/'registry/personas.yaml').write_text('personas:\n  - id: opaque-identity\n    name: Hana\n')
    souls,identity=reference_souls(tmp_path)
    assert souls=={'opaque-identity':'Assistant for Hana. History is from that user.'}
    assert identity['names_from_official_registry_not_fact_annotations'] is True
