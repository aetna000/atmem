"""Official host identity only; never reads task/fact annotations."""
from pathlib import Path
import hashlib


def reference_souls(upstream: Path):
    import yaml
    template_path=upstream/'harness/benchmark_soul.md'
    registry_path=upstream/'registry/personas.yaml'
    template=template_path.read_text()
    if template.count('{{persona_name}}')!=1:
        raise ValueError('official native identity placeholder changed')
    registry=yaml.safe_load(registry_path.read_text())
    souls={}
    for entry in registry['personas']:
        key,name=entry.get('id'),entry.get('name')
        if (not isinstance(key,str) or key in souls or not isinstance(name,str)
                or not name.strip() or len(name)>128 or '\n' in name):
            raise ValueError('official host identity metadata invalid')
        souls[key]=template.replace('{{persona_name}}',name)
    return souls,{'soul_template_sha256':hashlib.sha256(template_path.read_bytes()).hexdigest(),
                  'persona_registry_sha256':hashlib.sha256(registry_path.read_bytes()).hexdigest(),
                  'configured_soul_sha256':{p:hashlib.sha256(s.encode()).hexdigest() for p,s in souls.items()},
                  'names_from_official_registry_not_fact_annotations':True}
