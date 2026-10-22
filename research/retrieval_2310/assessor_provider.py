"""Transport-only wiring of the product AtBot state classifier to a budgeted proxy."""
from pathlib import Path
import os
import sys


class AtBotStateAssessor:
    egress_class='remote'
    identity={'role':'source-state-classification','provider':'Azure via OpenRouter',
              'model':'openai/gpt-5.6-sol','reasoning':'medium'}

    def __init__(self,gateway):
        source=Path(__file__).resolve().parents[2]/'packages/atbot/src'
        if str(source) not in sys.path:sys.path.insert(0,str(source))
        from atbot.providers.openai_compatible import OpenAICompatibleProvider
        os.environ['ATMEM_STATE_ASSESSOR_PROXY_TOKEN']=gateway.local_token
        self.provider=OpenAICompatibleProvider(name='azure-openrouter-state',model='openai/gpt-5.6-sol',
            endpoint=gateway.base_url,api_key_env='ATMEM_STATE_ASSESSOR_PROXY_TOKEN',egress_class='remote',
            timeout=65,reasoning_effort='medium',strict_schema=True)

    def __call__(self,query,evidence):
        from atbot.state_assessment import assess_state
        return assess_state(self.provider,query,evidence)


class AtBotInitialStateAssessor(AtBotStateAssessor):
    identity={**AtBotStateAssessor.identity,'role':'initial-source-state-classification'}

    def __call__(self,query,evidence):
        from atbot.state_assessment import assess_state
        return assess_state(self.provider,query,evidence,max_evidence=256,max_input_bytes=80000)


class AtBotSourceDossierAssessor(AtBotStateAssessor):
    identity={**AtBotStateAssessor.identity,'role':'query-specific-source-dossier-selection'}

    def __call__(self,query,evidence):
        from atbot.source_dossier import propose_dossier
        return propose_dossier(self.provider,query,evidence)
