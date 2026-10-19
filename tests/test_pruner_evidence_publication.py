import base64

from tools.publish_pruner_evidence import Redactor


def test_readable_export_decodes_before_redacting():
    secret = 'known_owner_credential_123456789'
    value = {'stdout_base64': base64.b64encode(
        ('/Users/javadtaghia token=' + secret).encode()).decode()}
    exported = Redactor([secret]).value(value)
    assert secret not in str(exported)
    assert 'stdout_base64' not in exported
    assert exported['stdout_text'] == '/Users/benchmark token=[REDACTED_CREDENTIAL]'


def test_redaction_preserves_measurements_and_nested_structure():
    value = {'runtime': ['torch 2.8.0+cu128', 'host 192.168.0.87'], 'tokens': 75178}
    result = Redactor().value(value)
    assert result == {'runtime': ['torch 2.8.0+cu128', 'host [REDACTED_IP]'], 'tokens': 75178}


def test_tokens_and_private_key_material_removed():
    text = ('hf_' + 'A' * 30 + '\n-----BEGIN OPENSSH PRIVATE KEY-----\n'
            'private bytes\n-----END OPENSSH PRIVATE KEY-----')
    result = Redactor().text(text)
    assert 'private bytes' not in result and 'hf_' not in result
    assert result.count('[REDACTED_CREDENTIAL]') == 2


def test_source_patches_are_readable_and_scanned():
    result = Redactor(['credential_123456789012']).value({'patch_source_bytes': {
        'src/example.py': base64.b64encode(b'credential_123456789012').decode(),
        'src/deleted.py': None}})
    assert result == {'patch_source_text': {'src/example.py': '[REDACTED_CREDENTIAL]', 'src/deleted.py': None}}
