"""Minimal human sign-in/consent pages, not an application dashboard."""
from __future__ import annotations

from collections import defaultdict,deque
import html
import json
import secrets
from pathlib import Path
import re
import time
from datetime import datetime,timezone
from urllib.parse import urlsplit, quote

from starlette.requests import Request
from starlette.responses import HTMLResponse,RedirectResponse,JSONResponse,PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import CODEX_CLIENT_ID
from .service import Denied
from .repository import AccountClosed

ASSETS = Path(__file__).with_name('assets')
STYLE = (ASSETS / 'account.css').read_text()
WORDMARK = (ASSETS / 'wordmark.svg').read_text()
NATIVE_SCRIPT = (ASSETS / 'account.js').read_text()


def page(title,body,status=200,*,validated_callback=None,native=False):
    form_action = "'self'"
    if validated_callback:
        # Chromium checks form-action on the 303 redirect as well as the form's POST.
        # Only the OAuth consent page gets its SDK-validated callback destination.
        target = urlsplit(validated_callback)
        form_action += f" {target.scheme}://{target.netloc}{quote(target.path, safe='/%')}"
    script_nonce = secrets.token_urlsafe(24) if native else None
    script = f'<script nonce="{script_nonce}">{NATIVE_SCRIPT}</script>' if native else ''
    policy = f"default-src 'none'; style-src 'unsafe-inline'; form-action {form_action}; frame-ancestors 'none'; base-uri 'none'"
    if native:
        policy += f"; script-src 'nonce-{script_nonce}'; connect-src 'self'"
    safe_title = html.escape(title)
    response = HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title} · AtMem</title><style>{STYLE}</style></head>
<body><div class="shell"><main><div class="brand" role="img" aria-label="AtMem">{WORDMARK}</div>
<h1 tabindex="-1">{safe_title}</h1>{body}</main><footer><a href="https://atmem.ai/cloud/privacy/">Privacy</a>
<a href="https://atmem.ai/cloud/terms/">Terms</a><a href="https://atmem.ai/cloud/support/">Support</a><a href="/account/delete">Delete account</a></footer></div>{script}</body></html>''', status_code=status)
    response.headers.update({"Cache-Control":"no-store", "Content-Security-Policy":policy, "Referrer-Policy":"same-origin", "X-Content-Type-Options":"nosniff"})
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
        account_email=request.method=='POST' and request.url.path in {'/register','/verify-email','/reset-password'}
        key=(request.client.host if request.client else 'unknown','account-email' if account_email else 'general')
        if key not in self.buckets and len(self.buckets)>=10000:
            return JSONResponse({"error":"rate_limited"},status_code=429,headers={"Retry-After":"60"})
        now=time.monotonic();bucket=self.buckets[key]
        while bucket and bucket[0]<=now-60:bucket.popleft()
        if len(bucket)>=(5 if account_email else self.settings.requests_per_minute):
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

    @mcp.custom_route('/account/delete',methods=['GET','POST'])
    async def delete_account(request:Request):
        """Fresh human authority only. No MCP tool exposes this operation."""
        proof_id=request.session.get('account_deletion')
        proof=repository.get_control('account-deletion',proof_id,deletion_retry=True) if proof_id else None
        if request.method=='GET':
            completed=request.session.get('deletion_receipt')
            if completed:
                return page('Account deletion receipt','<pre>'+html.escape(json.dumps(completed,indent=2))+'</pre>')
            if proof:
                receipt=repository.deletion_receipt(proof['subject'],proof_id)
                if receipt and receipt['firebase_account_deleted']:
                    return page('Account deletion receipt','<pre>'+html.escape(json.dumps(receipt,indent=2))+'</pre>')
                body='<p>Account: <strong>'+html.escape(proof.get('email',''))+'</strong></p><p>This deletes every personal and project memory in this AtMem Cloud account, including corrected versions, sources, audit data and pending actions. All plugin grants will be blocked immediately.</p><p>Your Firebase AtMem account will also be deleted. This does not delete your Google or ChatGPT account. Provider history, logs and ChatGPT copies are outside this deletion receipt. A non-content deletion fence remains to prevent resurrection.</p>'
                return page('Confirm account deletion',body+'<form method="post">'+csrf_form(request)+'<label><input type="checkbox" name="understood" value="yes" required> Delete my entire AtMem Cloud account and memory.</label><button name="decision" value="delete">Delete this entire account</button><button name="decision" value="cancel">Cancel</button></form>')
            return page('Delete AtMem Cloud account','<p>Sign in again to preview account-wide deletion. No data is deleted at this step.</p><form method="post">'+csrf_form(request)+credentials()+'<button name="decision" value="preview">Sign in and preview deletion</button></form>')
        try:
            form=await request.form();check_csrf(request,form)
            if form.get('decision')=='preview':
                identity_proof=await identity.authenticate(str(form.get('email','')),str(form.get('password','')),require_verified=False)
                current_id=request.session.get('human_session')
                current=repository.get_control('browser',current_id) if current_id else None
                if current and current['subject']!=identity_proof['subject']:raise Denied('wrong_account')
                proof_id=secrets.token_urlsafe(32)
                marker=repository._doc('account',identity_proof['subject']).get(timeout=5,retry=None)
                if marker.exists:proof_id=marker.to_dict()['deletion_id']
                repository.put_control('account-deletion',proof_id,{'subject':identity_proof['subject'],'email':identity_proof['email'],'id_token':identity_proof['id_token'],'expires_at':time.time()+300})
                request.session['account_deletion']=proof_id
                return RedirectResponse(settings.issuer+'/account/delete',status_code=303)
            if not proof:raise Denied('fresh_deletion_preview_required')
            if form.get('decision')=='cancel':
                # Once fencing has begun, cancellation must not reopen access.
                repository.assert_active(proof['subject'])
                repository._doc('account-deletion',proof_id).delete()
                request.session.pop('account_deletion',None)
                return page('Deletion cancelled','No account data was deleted.')
            if form.get('decision')!='delete' or form.get('understood')!='yes':raise Denied('explicit_account_confirmation_required')
            receipt=repository.purge_account(proof['subject'],proof_id)
            if not receipt['firebase_account_deleted']:
                await identity.delete_account(proof['id_token'])
            receipt['firebase_account_deleted']=True;receipt['completed_at']=time.time()
            repository.update_deletion_receipt(proof['subject'],receipt)
            # This five-minute encrypted proof permits lost-response recovery;
            # TTL removes it. It cannot reopen the fenced account.
            request.session.clear();request.session['deletion_receipt']=receipt
            return page('Account deleted','<p>Active service storage and the Firebase account were deleted. Keep this receipt; provider history and ChatGPT copies are separate.</p><pre>'+html.escape(json.dumps(receipt,indent=2))+'</pre>')
        except (ValueError,Denied,AccountClosed):
            partial=repository.deletion_receipt(proof['subject'],proof_id) if proof else None
            details='<pre>'+html.escape(json.dumps(partial,indent=2))+'</pre>' if partial else ''
            return page('Deletion not completed','The request was rejected, expired or Firebase deletion is not confirmed. If confirmation already began, account access remains blocked. Retry the same confirmation while it is valid or contact support; no complete deletion is claimed.'+details+'<form method="post">'+csrf_form(request)+credentials()+'<button name="decision" value="preview">Sign in again to retry deletion</button></form>',409)

    @mcp.custom_route('/.well-known/openai-apps-challenge',methods=['GET'])
    async def domain_challenge(request):
        if settings.openai_domain_challenge is None:
            return PlainTextResponse('Not configured',status_code=404)
        return PlainTextResponse(settings.openai_domain_challenge,headers={'Cache-Control':'no-store'})

    @mcp.custom_route('/health',methods=['GET'])
    async def health(request):
        return JSONResponse({'status':'ready','service':'atmem-chatgpt','version':'0.1.0','engine':'2.3.12','mode':'emulator' if settings.emulator else 'cloud'})

    @mcp.custom_route('/connect/{nonce}',methods=['GET','POST'])
    async def connect(request:Request):
        nonce=request.path_params['nonce']
        pending=repository.get_control('authorize',nonce)
        if pending is None:
            return page('This sign-in request has ended',
                        '<p>Return to the chat that requested AtMem. Ask AtMem again and choose the sign-in or reconnect action to start a fresh request.</p>', 400)
        if request.method=='GET':
            native = pending['client_id'] == CODEX_CLIENT_ID
            client = 'Codex' if native else 'your app'
            labels = {'memory:read':'Read saved memories', 'memory:write':'Propose saves and corrections',
                      'memory:delete':'Propose deletions'}
            permissions = ' · '.join(labels[scope] for scope in pending['params'].get('scopes') or ['memory:read'])
            links = ''
            if settings.access_policy == 'registered':
                links = (f'<nav class="links" aria-label="Account help"><a href="/register?request={nonce}">Create account</a>'
                         f'<a href="/reset-password?request={nonce}">Reset password</a>'
                         f'<a href="/verify-email?request={nonce}">Verify email</a></nav>')
            attribute = ' data-native' if native else ''
            body = (f'<section id="login"><p>Sign in to use your saved memories in {client}.</p>'
                    f'<div class="scope">{permissions}<br>Each change needs your separate approval.</div>'
                    f'<form method="post"{attribute}>'+csrf_form(request)+credentials()
                    +'<div class="controls"><button name="decision" value="approve">Sign in and allow</button>'
                    '<button name="decision" value="deny" formnovalidate>Cancel</button></div></form>'+links+'</section>'
                    '<p id="feedback" role="alert"></p><p id="progress" role="status" hidden>Waiting for Codex to finish signing in.</p>'
                    )
            return page('Connect to AtMem',body,validated_callback=pending['params']['redirect_uri'],native=native)
        try:
            form=await request.form();check_csrf(request,form)
            approved=form.get('decision')=='approve'
            account=await browser_user(request,form) if approved else ''
            enhanced = approved and pending['client_id'] == CODEX_CLIENT_ID and request.headers.get('accept') == 'application/json'
            receipt = secrets.token_urlsafe(32) if enhanced else None
            callback = provider.finish_authorize(nonce,account,approved,connection_receipt=receipt)
            if receipt:
                request.session['connection_receipt'] = receipt
                return JSONResponse({'callback':callback, 'status':'/connection/status/'+receipt})
            return RedirectResponse(callback,status_code=303)
        except (ValueError,Denied) as error:
            if str(error)=='verify_email_before_connecting':
                return page('Verify your email','Verify your Firebase email address before connecting. Return to the connection page to resend verification if needed.',403)
            return page('Connection rejected','Sign-in failed, consent expired or the request was invalid. Start account linking again.',403)

    @mcp.custom_route('/connection/status/{receipt}',methods=['GET'])
    async def connection_status(request:Request):
        receipt = request.path_params['receipt']
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', receipt) or not secrets.compare_digest(request.session.get('connection_receipt',''),receipt):
            return JSONResponse({'error':'unknown_connection'},status_code=404)
        connected = bool(repository.get_control('connection-receipt',receipt))
        if connected:
            request.session['completed_connection'] = receipt
        return JSONResponse({'connected':connected})

    @mcp.custom_route('/connection/complete',methods=['GET'])
    async def connection_complete(request:Request):
        if not request.session.get('completed_connection') or request.session.get('completed_connection') != request.session.get('connection_receipt'):
            return page('Connection unconfirmed','<p>Return to your chat to connect your AtMem account.</p>',400)
        return page('You’re connected','<div class="mark" aria-hidden="true">✓</div>'
                    '<p>Your AtMem account is connected to Codex.</p>'
                    '<div class="scope">Return to your chat to continue your request. You can close this tab.</div>')

    @mcp.custom_route('/register',methods=['GET','POST'])
    @mcp.custom_route('/verify-email',methods=['GET','POST'])
    @mcp.custom_route('/reset-password',methods=['GET','POST'])
    async def account_access(request:Request):
        nonce=request.query_params.get('request','')
        if settings.access_policy!='registered' or not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',nonce) or repository.get_control('authorize',nonce) is None:
            return page('Start from ChatGPT','Begin connecting AtMem in ChatGPT to register or recover access.',400)
        operation=request.url.path
        title={'/register':'Register for AtMem','/verify-email':'Resend verification','/reset-password':'Reset password'}[operation]
        if request.method=='GET':
            inputs=credentials() if operation!='/reset-password' else '<label>Email <input type="email" name="email" required autocomplete="username" maxlength="254"></label>'
            notice='<p>AtMem stores only memories you explicitly save. This is a cloud service: encrypted memory is held in Google Cloud, the operator holds the key, and requested results are sent to ChatGPT. Firebase manages account credentials. No conversations are automatically captured.</p>'
            if operation=='/register':
                inputs+='<p>Use a password of at least 12 characters.</p><label><input type="checkbox" name="understood" value="yes" required> I understand this cloud data flow and want to create an account.</label>'
            return page(title,notice+'<form method="post">'+csrf_form(request)+inputs+'<button>'+title+'</button></form><p><a href="/connect/'+nonce+'">Return to sign in</a></p>')
        try:
            form=await request.form();check_csrf(request,form)
            email=str(form.get('email','')).strip();password=str(form.get('password',''))
            if not 3<=len(email)<=254:raise ValueError('invalid_email')
            if operation=='/register' and (form.get('understood')!='yes' or not 12<=len(password)<=256):raise ValueError('consent_or_password_required')
            if not repository.claim_email_slot(email):
                return page('Please wait','Wait two minutes before requesting another account email.',429)
            if operation=='/register':await identity.register(email,password)
            elif operation=='/verify-email':await identity.resend_verification(email,password)
            else:await identity.reset_password(email)
            return page('Check your email','<p>If the account details are eligible, Firebase will send the requested email. Complete its steps, then sign in to connect. If linking expires, start again from ChatGPT.</p><p><a href="/connect/'+nonce+'">Return to sign in</a></p>')
        except (ValueError,Denied):
            return page('Request rejected','Check the supplied details and cloud consent. No memory access was granted.',400)

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

