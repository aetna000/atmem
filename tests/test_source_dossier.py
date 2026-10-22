from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from atmem.context_engine.source_dossier import validate_source_dossier

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/atbot/src'))
from atbot.source_dossier import propose_dossier


def test_companion_and_independent_host_keep_exact_quotes_without_generated_facts():
    evidence=[{'unit_id':'one','text':'设置保持不变，但仅在测试环境中。'}]
    class Provider:
        def complete(self,**kwargs):
            assert kwargs['schema']['additionalProperties'] is False
            assert 'do not paraphrase' in kwargs['system'].lower()
            return SimpleNamespace(structured={'needs':[{'need':'Configuration and scope',
                'quotes':[{'unit_id':'one','quote':evidence[0]['text']}]}],
                'unresolved_needs':[]},provider='fixture',model='fixture',input_tokens=1,output_tokens=1)
    value=propose_dossier(Provider(),'What configuration applies?',evidence)
    assert validate_source_dossier(value,evidence)==value
    assert value['authority_decision'] is None and value['canonical_storage'] is False
    for key,replacement in [('unit_id','foreign'),('quote','Invented fact')]:
        import copy
        bad=copy.deepcopy(value);bad['needs'][0]['quotes'][0][key]=replacement
        with pytest.raises(ValueError):validate_source_dossier(bad,evidence)
