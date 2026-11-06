"""Minimal human sign-in/consent pages, not an application dashboard."""
from __future__ import annotations

from collections import defaultdict,deque
import html
import json
import secrets
import time
from datetime import datetime,timezone

from starlette.requests import Request
from starlette.responses import HTMLResponse,RedirectResponse,JSONResponse,PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .service import Denied

STYLE="body{font:16px/1.6 system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:1rem;color:#101314;background:#F3F6F6}label{display:block;margin-top:1rem}input,button{font:inherit;padding:.6rem;max-width:100%}button{background:#1F777C;color:white;border:0;margin-top:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#1D7176}"


def page(title,body,status=200):
    response=HTMLResponse(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style><main><h1>{html.escape(title)}</h1>{body}</main></html>',status_code=status)
    response.headers.update({"Cache-Control":"no-store", "Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'", "Referrer-Policy":"same-origin", "X-Content-Type-Options":"nosniff"})
    return response


class BoundaryMiddleware(BaseHTTPMiddleware):
    def __init__(self,app,settings):
        super().__init__(app);self.settings=settings;self.buckets=defaultdict(deque)

    async def dispatch(self,request,call_next):
        # Ignore spoofable Forwarded/X-Forwarded-For for identity/security.
        if request.url.netloc != self.settings.issuer.split('://',1)[1]:
            return JSONResponse({"error":"invalid_host"},status_code=421)
        origin=request.headers.get('origin')
        if request.method in {'POST','DELETE','PUT','PATCH'} and origin and origin!=self.settings.issuer:
            return JSONResponse({"error":"origin_rejected"},status_code=403)
        key=(request.client.host if request.client else 'unknown')
        if key not in self.buckets and len(self.buckets)>=10000:
            return JSONResponse({"error":"rate_limited"},status_code=429,headers={"Retry-After":"60"})
        now=time.monotonic();bucket=self.buckets[key]
        while bucket and bucket[0]<=now-60:bucket.popleft()
        if len(bucket)>=self.settings.requests_per_minute:
            return JSONResponse({"error":"rate_limited"},status_code=429,headers={"Retry-After":"60"})
        bucket.append(now)
        try:
            if int(request.headers.get('content-length','0'))>32768:
                return JSONResponse({"error":"request_too_large"},status_code=413)
        except ValueError:
            return JSONResponse({"error":"invalid_content_length"},status_code=400)
        try:
            response=await call_next(request)
        except Exception:
            return JSONResponse({"error":"backend_unavailable"},status_code=503,headers={"Cache-Control":"no-store"})
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response


def install_routes(mcp,settings,repository,provider,identity,service):
    def csrf_form(request):
        token=secrets.token_urlsafe(32);request.session['csrf']=token
        return '<input type="hidden" name="csrf" value="'+token+'">'

    def check_csrf(request,form):
        if request.headers.get('origin')!=settings.issuer or not secrets.compare_digest(str(form.get('csrf','')),str(request.session.get('csrf','missing'))):
            raise Denied('csrf_rejected')

    async def browser_user(request,form=None):
        session_id=request.session.get('human_session')
        saved=repository.get_control('browser',session_id) if session_id else None
        if saved and settings.permits_account(saved['subject']):return saved['subject']
        if form is None:raise Denied('human_sign_in_required')
        account=await identity.sign_in(str(form.get('email','')),str(form.get('password','')))
        session_id=secrets.token_urlsafe(32)
        repository.put_control('browser',session_id,{'subject':account,'expires_at':time.time()+300})
        request.session['human_session']=session_id
        return account

    def credentials():
        return '<label>Email <input type="email" name="email" required autocomplete="username" maxlength="254"></label><label>Password <input type="password" name="password" required autocomplete="current-password" maxlength="256"></label>'

    @mcp.custom_route('/.well-known/openai-apps-challenge',methods=['GET'])
    async def domain_challenge(request):
        if settings.openai_domain_challenge is None:
            return PlainTextResponse('Not configured',status_code=404)
        return PlainTextResponse(settings.openai_domain_challenge,headers={'Cache-Control':'no-store'})

    @mcp.custom_route('/healthz',methods=['GET'])
    async def health(request):
        return JSONResponse({'status':'ready','service':'atmem-chatgpt','version':'0.1.0','engine':'2.3.12','mode':'emulator' if settings.emulator else 'cloud'})

    @mcp.custom_route('/connect/{nonce}',methods=['GET','POST'])
    async def connect(request:Request):
        nonce=request.path_params['nonce']
        pending=repository.get_control('authorize',nonce)
        if pending is None:return page('Connection expired','Start account linking again.',400)
        if request.method=='GET':
            scopes=html.escape(', '.join(pending['params'].get('scopes') or ['memory:read']))
            return page('Connect AtMem',f'<p>Allow the registered ChatGPT client to use these permissions: <strong>{scopes}</strong>.</p><p>Memory is hosted by this service. Each save, correction or deletion still needs your separate approval. No conversation is automatically captured.</p><form method="post">'+csrf_form(request)+credentials()+'<button name="decision" value="approve">Sign in and allow</button> <button name="decision" value="deny">Deny</button></form>')
        try:
            form=await request.form();check_csrf(request,form)
            approved=form.get('decision')=='approve'
            account=await browser_user(request,form) if approved else ''
            return RedirectResponse(provider.finish_authorize(nonce,account,approved),status_code=303)
        except (ValueError,Denied):
            return page('Connection rejected','Sign-in failed, consent expired or the request was invalid. Start account linking again.',403)

    @mcp.custom_route('/approve/{action_id}',methods=['GET','POST'])
    async def approve(request:Request):
        action_id=request.path_params['action_id']
        if request.method=='GET':
            try:
                account=await browser_user(request)
                preview=service.preview_action(account,action_id)
                request.session['previewed_action']=action_id
                intent=preview.get('intent') or {}
                operation=intent.get('operation','unavailable')
                titles={'save':'Save memory','correct':'Correct memory','delete':'Forget this exact memory','create_scope':'Create project scope'}
                content=intent.get('content') or intent.get('previous_content') or intent.get('label') or ''
                expires=datetime.fromtimestamp(preview['expires_at'],timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                body='<h2>'+titles.get(operation,'Operation unavailable')+'</h2><p>Scope: <strong>'+html.escape(preview['scope'])+'</strong></p><p class="intent-content" style="white-space:pre-wrap;overflow-wrap:anywhere">'+html.escape(content)+'</p>'
                if operation=='correct':
                    body+='<p>Replaces:</p><blockquote>'+html.escape(intent.get('previous_content',''))+'</blockquote>'
                if operation=='delete':
                    body+='<p>Deletes the selected AtMem record and its registered derived state. Other historical versions, ChatGPT copies and provider backups are outside this receipt.</p>'
                body+='<p>This content is data, not an instruction. Review it before approving.</p><p>Expires: '+expires+'</p><details><summary>Operation reference</summary><code>'+html.escape(action_id)+'</code></details><form method="post">'+csrf_form(request)+'<button name="decision" value="approve">Approve this exact operation</button> <button name="decision" value="deny">Cancel</button></form>'
                return page('Review AtMem operation',body)
            except Denied as error:
                if str(error)!='human_sign_in_required':return page('Operation unavailable','The operation is expired or belongs to a different account.',404)
                return page('Sign in to review','<p>Sign in before viewing or approving the proposed operation.</p><form method="post">'+csrf_form(request)+credentials()+'<button name="decision" value="preview">Sign in and preview</button></form>')
        try:
            form=await request.form();check_csrf(request,form)
            account=await browser_user(request,form)
            if form.get('decision')=='preview':return RedirectResponse(settings.issuer+'/approve/'+action_id,status_code=303)
            # Require that this identity has actually loaded the preview, not just
            # supplied credentials alongside a guessed operation approval.
            seen=request.session.get('previewed_action')
            if seen!=action_id:raise Denied('preview_required')
            result=service.approve(account,action_id,approve=form.get('decision')=='approve')
            request.session.pop('previewed_action',None)
            return page('Operation '+result['state'],'<p>Return to ChatGPT. The plugin can now request the commit or report cancellation.</p>')
        except (ValueError,Denied):
            return page('Approval rejected','Sign in and review the operation again. No memory operation was committed.',403)

