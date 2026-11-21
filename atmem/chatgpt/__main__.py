"""Explicit service entrypoint. No account creation or infrastructure provisioning."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets


def main():
    parser=argparse.ArgumentParser(description='Cloud AtMem MCP service (optional dependencies required)')
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init-test',help='Create only isolated loopback emulator configuration; never a public deployment')
    init.add_argument('--directory',required=True);init.add_argument('--port',type=int,default=8769)
    serve=sub.add_parser('serve');serve.add_argument('--config',required=True);serve.add_argument('--port',type=int,default=None)
    serve.add_argument('--host',default='127.0.0.1')
    args=parser.parse_args()
    if args.command=='init-test':
        root=Path(args.directory).expanduser().resolve()
        native=(Path.home()/'.atmem').resolve()
        if root==native or native in root.parents:
            raise SystemExit('Refusing to initialize inside native ~/.atmem')
        if root.exists() and any(root.iterdir()):
            raise SystemExit('Refusing to overwrite an existing directory; reuse its config for repeated startup')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        key=root/'service.key';fd=os.open(key,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32)+'\n')
        config={'home':str(root/'home'),'key_file':str(key),'project':'demo-atmem-plugin',
            'issuer':f'http://127.0.0.1:{args.port}','firebase_api_key':'emulator-only-not-a-secret',
            'emulator':True,'clients':{'atmem-test-client':['http://127.0.0.1:9901/callback']},'requests_per_minute':1000}
        (root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
        print(json.dumps({'config':str(root/'config.json'),'test_only':True,'key_exposed':False}))
    else:
        from .config import Settings
        settings=Settings.load(args.config)
        from .server import create_app
        import uvicorn
        from urllib.parse import urlparse
        port=args.port or urlparse(settings.issuer).port or int(os.environ.get('PORT','8080'))
        if not settings.emulator and os.environ.get('K_SERVICE') and args.host!='0.0.0.0':
            raise SystemExit('Cloud Run requires --host 0.0.0.0 and a configured HTTPS public issuer')
        # Access logs contain approval/code URLs; disable them. Protocol logs
        # are limited to warnings and must never log incoming arguments/tokens.
        uvicorn.run(create_app(settings),host=args.host,port=port,access_log=False,log_level='warning',proxy_headers=False)

if __name__=='__main__':main()
