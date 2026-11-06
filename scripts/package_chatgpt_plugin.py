#!/usr/bin/env python3
"""Reproducible development ZIP; gated public upload generation and readiness report."""
from __future__ import annotations
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'plugins/atmem-chatgpt'
CATEGORIES={'Business & Operations','Communication','Creativity','Data & Analytics','Developer Tools','Education & Research','Entertainment','Finance','Healthcare','Other','Productivity','Scientific Research','Security','Travel'}


def load_files():
    files={str(p.relative_to(SOURCE)):p.read_bytes() for p in SOURCE.rglob('*') if p.is_file() and not p.is_symlink()}
    for name in ['SETUP.md','ARCHITECTURE.md','OPERATIONS.md','PRIVACY-DRAFT.md','TERMS-SUPPORT-DRAFT.md','SUBMISSION.md','CHANGELOG.md']:
        files['references/'+name]=(ROOT/'docs/chatgpt'/name).read_bytes()
    return files


def validate(files:dict[str,bytes], *, public=False)->list[str]:
    import jsonschema
    errors=[]
    for name in ['plugin','mcp']:
        try:
            value=json.loads(files[name+'.json'])
            if name=='mcp':
                # The published Agent Plugins 1.0 transport schema predates the
                # per-server OpenAI extensions documented by OpenAI. Validate
                # the transport projection strictly, then its OAuth extension
                # below. This is not a claim the unchanged schema accepts it.
                value=json.loads(json.dumps(value))
                for server in value['mcpServers'].values():server.pop('extensions',None)
            schema=json.loads((ROOT/f'tests/fixtures/chatgpt/{name}.schema.json').read_text())
            jsonschema.Draft202012Validator(schema).validate(value)
        except Exception as error:errors.append(f'{name} schema: {error}')
    if errors:return errors
    manifest=json.loads(files['plugin.json']);mcp=json.loads(files['mcp.json'])
    extension=manifest['extensions']['com.openai'];interface=extension['interface']
    if len(interface['displayName'])>30 or len(interface['shortDescription'])>30:errors.append('listing title/subtitle exceeds 30 characters')
    if interface.get('category') not in CATEGORIES:errors.append('unsupported listing category')
    if not isinstance(interface.get('capabilities'),list):errors.append('capabilities must be an array')
    for key in ['logo','composerIcon','logoDark','composerIconDark']:
        path=interface.get(key,'').removeprefix('./')
        if path not in files or '..' in Path(path).parts:errors.append('missing/unsafe '+key)
        elif not files[path].startswith(b'\x89PNG\r\n\x1a\n'):errors.append('icon is not PNG')
        else:
            import struct
            w,h=struct.unpack('>II',files[path][16:24])
            if w!=h or not 256<=w<=4096 or len(files[path])>5*1024*1024:errors.append('icon size out of bounds')
    if not any(p.startswith('skills/') and p.endswith('/SKILL.md') for p in files):errors.append('missing usable skill')
    if '.app.json' in files or extension.get('apps') is not None or manifest.get('apps') is not None:errors.append('public-incompatible app binding')
    if any('hooks/' in p or 'node_modules/' in p or Path(p).name.endswith(('.key','.db')) for p in files):errors.append('unexpected runtime/secret files')
    cases=extension.get('review',{}).get('test_cases',{})
    if len(cases.get('positive',[]))!=5 or len(cases.get('negative',[]))!=3:errors.append('review needs exactly five positive and three negative cases')
    for case in cases.get('positive',[]):
        if any(not isinstance(case.get(k),str) or not case[k].strip() for k in ['description','prompt','tools_triggered','expected_behavior']):errors.append('incomplete positive case')
    for server in mcp['mcpServers'].values():
        if server.get('headers'):errors.append('nonempty public server headers forbidden')
        auth=server.get('extensions',{}).get('com.openai',{}).get('auth',{})
        if auth.get('type')!='oauth':errors.append('private memory must use OAuth')
        client=auth.get('client',{})
        if client.get('mode')=='provided':
            if not client.get('clientId') or client.get('tokenEndpointAuthMethod')!='none':errors.append('provided PKCE OAuth client metadata missing')
        elif client.get('mode')=='cimd':
            if set(client)!={'mode'}:errors.append('CIMD must not include client credentials or provided-client fields')
        else:errors.append('supported PKCE OAuth client metadata missing')
        if 'clientSecret' in auth or 'clientSecret' in client:errors.append('client secret forbidden in package')
    if public:
        for key in ['websiteURL','supportURL','privacyPolicyURL','termsOfServiceURL']:
            url=interface.get(key,'');parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:errors.append('missing verified '+key)
        for server in mcp['mcpServers'].values():
            parsed=urlparse(server.get('url',''))
            if parsed.scheme!='https' or not parsed.hostname or parsed.hostname in {'localhost','127.0.0.1'} or parsed.hostname.endswith(('.invalid','.example')) or 'SET_' in server.get('url',''):errors.append('public stable HTTPS endpoint not configured')
        if not extension.get('review',{}).get('demo_recording_url'):errors.append('actual reviewer-accessible demo recording missing')
        if not interface.get('developerName'):errors.append('intended verified publisher name not supplied')
    return errors


def archive(output:Path,files:dict[str,bytes]):
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,data in sorted(files.items()):
            info=zipfile.ZipInfo('atmem-chatgpt/'+path,date_time=(2026,11,6,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(output) as z:
        readback={str(Path(name).relative_to('atmem-chatgpt')):z.read(name) for name in z.namelist()}
    assert readback==files
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--public',action='store_true');parser.add_argument('--readiness',action='store_true');parser.add_argument('--metadata',type=Path);parser.add_argument('--verification-record',type=Path)
    args=parser.parse_args()
    files=load_files()
    # Public metadata must be deliberately supplied, not inferred from the site.
    if args.metadata:
        override=json.loads(args.metadata.read_text())
        manifest=json.loads(files['plugin.json']);mcp=json.loads(files['mcp.json'])
        manifest['extensions']['com.openai']['interface'].update(override.get('interface',{}))
        manifest['extensions']['com.openai']['review'].update(override.get('review',{}))
        if 'mcp' in override:mcp=override['mcp']
        files['plugin.json']=(json.dumps(manifest,indent=2)+'\n').encode();files['mcp.json']=(json.dumps(mcp,indent=2)+'\n').encode()
    errors=validate(files,public=args.public or args.readiness)
    if args.readiness:
        print(json.dumps({'development_contract_valid':not validate(files),'validation_profile':'Strict Agent Plugins 1.0 transport projection plus documented OpenAI extension checks; full portal scan not run','public_ready':False,'public_metadata_complete':not errors,'gaps':errors,
            'dashboard_checks':['verified individual publisher/org/project permissions','owned public endpoint/domain challenge','secure synthetic reviewer login','actual account read/write/invocation checks','required scans and legal attestations','country targeting and billing/retention decisions']},indent=2));return
    if errors:raise SystemExit('\n'.join(errors))
    if args.public:
        # Validate actual unauthenticated discovery and relevant listing content,
        # never authenticate or read a real memory during package preparation.
        for key in ['websiteURL','supportURL','privacyPolicyURL','termsOfServiceURL']:
            url=json.loads(files['plugin.json'])['extensions']['com.openai']['interface'][key]
            with urllib.request.urlopen(url,timeout=15) as response:
                body=response.read(2*1024*1024).decode('utf-8',errors='replace')
            if 'AtMem' not in body:raise SystemExit('public listing URL does not identify AtMem: '+key)
        if not args.verification_record:
            raise SystemExit('Public build requires a reviewed verification record; see docs/chatgpt/SUBMISSION.md')
        verified=json.loads(args.verification_record.read_text())
        required=['verified_individual_publisher','organization_project_access','public_endpoint_oauth_tested','domain_ownership','policy_urls_reviewed','recording_playback_verified','synthetic_reviewer_access_verified','actual_chatgpt_read_write_results_recorded']
        if any(verified.get(k) is not True for k in required):raise SystemExit('public verification record is incomplete')
        # These are operator-recorded checks, not automated identity verification
        # or review approval. The portal remains authoritative for those states.
    if not args.output:raise SystemExit('--output is required for development package')
    print(json.dumps({'archive':str(args.output),'sha256':archive(args.output,files),'files':len(files),'development_only':not args.public}))

if __name__=='__main__':main()
