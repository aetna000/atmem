"""Run installed, scoped evidence discovery without a model or API key.

The owner explicitly supplies a new encrypted database and source text. This
application-owned scope/authorization is a demo boundary, not remote-user auth.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from atmem import Memory
from atmem.context_engine.contracts import ContextRequestV3
from atmem.context_engine.discovery_mcp import EvidenceDiscoveryMCP
from atmem.context_engine.navigator import NavigationBudget
from atmem.contracts import AuthorityScope, EpisodeIngestRequest, EpisodePart
from atmem.extract.validation import screen_content
from atmem.service.household import HouseholdApplication


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--text',required=True)
    parser.add_argument('--query',required=True)
    parser.add_argument('--mcp',action='store_true',help='Serve only memory_search and memory_inspect over stdio')
    args=parser.parse_args()
    if args.database.exists():
        raise SystemExit('Choose a new database path; this example never overwrites or migrates existing data.')
    if not args.text.strip() or not args.query.strip():
        raise SystemExit('Source text and query must be nonempty.')
    if not screen_content(args.text,trusted=True).admissible or not screen_content(args.query,trusted=True).admissible:
        raise SystemExit('Source text or query failed safety screening; no database was created.')
    HouseholdApplication.initialize(args.database,encrypted=True,backend='file')
    scope=AuthorityScope('local-owner','local-agent','local-workspace')
    principal='local-history-import'
    authority={'principal_id':principal,**scope.to_dict(),'scopes':['history_import:review']}
    memory=Memory(args.database,auto_vectors=False,review_authorities=(authority,))
    try:
        episode='source-'+uuid4().hex
        memory.form_context_episode(EpisodeIngestRequest(
            episode_id=episode,idempotency_key=episode,scope=scope,
            parts=(EpisodePart(part_id='text',ordinal=0,kind='text',source_type='user_message',
                content=args.text,content_sha256='sha256:'+sha256(args.text.encode()).hexdigest()),),
            binding_method='host_asserted',binding_assurance='host_asserted',
            source_observation_granularity='sentence'),history_import_principal=principal)
        memory.freeze_context_engine(scope)
        generation=memory.context_generation(scope)
        request=ContextRequestV3(context_id='example-context',request_id='example-request',
            scope=scope,query=args.query,profile_id='context-fast',mode='active',
            generation=generation['canonical_generation'],turn_id='example-turn')
        session=memory.open_evidence_discovery(request,
            authorize=lambda supplied:supplied.scope==scope,
            budget=NavigationBudget(max_operations=8,max_bytes=96000,max_elapsed_ms=120000))
        if args.mcp:
            EvidenceDiscoveryMCP(session).serve()
        else:
            result=session.search(args.query)
            print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        memory.close()


if __name__=='__main__':main()
