"""OAuth 2.1 provider using Firebase Auth for human identity, never memory tools.

PKCE and client/redirect validation are supplied by the MCP SDK handlers. Opaque
credentials are indexed by keyed hashes and encrypted in Firestore. Passwords
are only forwarded to Firebase's sign-in API; they are never retained/logged.
"""
from __future__ import annotations

import base64
import json
import hashlib
import secrets
import re
import time
from urllib.parse import urlencode

import httpx
from pydantic import AnyUrl
from mcp.server.auth.provider import AuthorizationCode, AuthorizationParams, AccessToken, RefreshToken, AuthorizeError, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .config import Settings, SCOPES, LOGIN_WINDOW_SECONDS
from .repository import Repository,AccountClosed


CODEX_CLIENT_ID = "https://chatgpt.com/oauth/codex/client.json"
CODEX_CALLBACKS = {"http://127.0.0.1/callback", "http://localhost/callback"}


class CodexNativeClient(OAuthClientInformationFull):
    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        # The native client chooses an available listener port at sign-in.
        # Vary only that port on a callback actually listed by this client.
        if redirect_uri is not None and redirect_uri.port:
            match = re.fullmatch(r'(http://(?:127\.0\.0\.1|localhost)):[0-9]+(/callback)', str(redirect_uri))
            if match and match[1] + match[2] in {str(uri) for uri in self.redirect_uris or []}:
                return redirect_uri
        return super().validate_redirect_uri(redirect_uri)


class FirebaseIdentity:
    def __init__(self, settings: Settings, repository: Repository | None = None):
        self.settings = settings
        self.repository = repository

    async def _request(self, method: str, payload: dict):
        if self.settings.emulator:
            import os
            base = "http://" + os.environ["FIREBASE_AUTH_EMULATOR_HOST"] + "/identitytoolkit.googleapis.com/v1"
        else:
            base = "https://identitytoolkit.googleapis.com/v1"
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            return await client.post(base + "/accounts:" + method,
                params={"key":self.settings.firebase_api_key}, json=payload)

    def _bound_identity(self, response) -> tuple[str, dict]:
        if response.status_code != 200:
            raise ValueError("sign_in_rejected")
        uid = response.json().get("localId")
        if not isinstance(uid, str) or not uid or len(uid)>128:
            raise ValueError("sign_in_rejected")
        # Trusted direct Firebase response, never a client-supplied JWT. This
        # project binding is not a general-purpose unsigned JWT verifier.
        try:
            encoded=response.json()["idToken"].split(".")[1]
            claims=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
            if claims.get("aud")!=self.settings.project or claims.get("iss")!="https://securetoken.google.com/"+self.settings.project or claims.get("sub")!=uid or claims.get("exp",0)<=time.time():
                raise ValueError("identity_project_mismatch")
        except (KeyError,IndexError,TypeError,ValueError,AttributeError):
            raise ValueError("sign_in_rejected") from None
        return uid, claims

    async def authenticate(self, email: str, password: str, *, require_verified=True) -> dict:
        if not 3 <= len(email) <= 254 or not 1 <= len(password) <= 256:
            raise ValueError("sign_in_rejected")
        response=await self._request("signInWithPassword", {"email":email,"password":password,"returnSecureToken":True})
        uid,claims=self._bound_identity(response)
        if require_verified and self.settings.access_policy == "registered" and claims.get("email_verified") is not True:
            raise ValueError("verify_email_before_connecting")
        if not self.settings.permits_account(uid):
            raise ValueError("account_not_invited")
        return {'subject':uid,'email':response.json().get('email',email),'id_token':response.json()['idToken'],'refresh_token':response.json()['refreshToken']}

    async def sign_in(self, email: str, password: str) -> str:
        identity=await self.authenticate(email,password)
        uid=identity['subject']
        if self.repository:
            try:self.repository.assert_active(uid)
            except AccountClosed:raise ValueError('account_deleted') from None
        if self.repository and self.settings.access_policy == 'registered':
            self.repository.put_control('firebase-identity',uid,{'refresh_token':identity['refresh_token'],'expires_at':time.time()+86400})
        return uid

    async def delete_account(self, id_token: str) -> None:
        response=await self._request('delete',{'idToken':id_token})
        if response.status_code!=200 and response.json().get('error',{}).get('message')!='USER_NOT_FOUND':
            raise ValueError('firebase_deletion_not_confirmed')

    async def revalidate(self, account: str) -> None:
        """Re-check Firebase on registered-account OAuth refresh, not passwords."""
        if self.settings.access_policy != 'registered':return
        saved=self.repository.get_control('firebase-identity',account) if self.repository else None
        if not saved:raise ValueError('firebase_reauthentication_required')
        if self.settings.emulator:
            import os
            url='http://'+os.environ['FIREBASE_AUTH_EMULATOR_HOST']+'/securetoken.googleapis.com/v1/token'
        else:url='https://securetoken.googleapis.com/v1/token'
        async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
            response=await client.post(url,params={'key':self.settings.firebase_api_key},data={'grant_type':'refresh_token','refresh_token':saved['refresh_token']})
        if response.status_code!=200:raise ValueError('firebase_reauthentication_required')
        value=response.json()
        # Same trusted-response/project checks as initial sign-in.
        from types import SimpleNamespace
        uid,claims=self._bound_identity(SimpleNamespace(status_code=200,json=lambda:{'localId':value.get('user_id'),'idToken':value.get('id_token')}))
        if uid!=account or claims.get('email_verified') is not True:raise ValueError('firebase_reauthentication_required')
        self.repository.put_control('firebase-identity',account,{'refresh_token':value['refresh_token'],'expires_at':time.time()+86400})

    async def register(self, email: str, password: str) -> None:
        if self.settings.access_policy != "registered":
            raise ValueError("registration_unavailable")
        if not 3 <= len(email) <= 254 or not 12 <= len(password) <= 256:
            raise ValueError("registration_rejected")
        response=await self._request("signUp", {"email":email,"password":password,"returnSecureToken":True})
        if response.status_code != 200:
            # Do not reveal whether an address already belongs to an account.
            if response.json().get("error",{}).get("message") == "EMAIL_EXISTS":
                return
            raise ValueError("registration_rejected")
        self._bound_identity(response)
        sent=await self._request("sendOobCode", {"requestType":"VERIFY_EMAIL","idToken":response.json()["idToken"]})
        if sent.status_code != 200:
            raise ValueError("verification_delivery_failed")

    async def resend_verification(self, email: str, password: str) -> None:
        if self.settings.access_policy != "registered" or not 3<=len(email)<=254 or not 1<=len(password)<=256:
            raise ValueError("verification_rejected")
        response=await self._request("signInWithPassword", {"email":email,"password":password,"returnSecureToken":True})
        self._bound_identity(response)
        sent=await self._request("sendOobCode", {"requestType":"VERIFY_EMAIL","idToken":response.json()["idToken"]})
        if sent.status_code != 200:raise ValueError("verification_delivery_failed")

    async def reset_password(self, email: str) -> None:
        if self.settings.access_policy != "registered" or not 3<=len(email)<=254:
            raise ValueError("reset_rejected")
        response=await self._request("sendOobCode", {"requestType":"PASSWORD_RESET","email":email})
        if response.status_code != 200 and response.json().get("error",{}).get("message") != "EMAIL_NOT_FOUND":
            raise ValueError("reset_rejected")


class OAuthProvider:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings; self.repository = repository
        self.identity = FirebaseIdentity(settings,repository)
        self.client_cache = {}

    async def get_client(self, client_id: str):
        callbacks = self.settings.clients.get(client_id)
        if callbacks is None:
            return await self.cimd_client(client_id)
        return OAuthClientInformationFull(client_id=client_id, client_secret=None,
            redirect_uris=list(callbacks), token_endpoint_auth_method="none",
            grant_types=["authorization_code","refresh_token"], response_types=["code"], scope=" ".join(SCOPES))

    async def cimd_client(self, client_id: str):
        if not re.fullmatch(r'https://chatgpt\.com/oauth/(?:[A-Za-z0-9_-]{1,128}/)?client\.json',client_id):return None
        cached=self.client_cache.get(client_id)
        if cached and cached[0]>time.monotonic():return cached[1]
        try:
            async with httpx.AsyncClient(timeout=5,follow_redirects=False) as client:
                async with client.stream('GET',client_id) as response:
                    if response.status_code!=200:return None
                    body=bytearray()
                    async for piece in response.aiter_bytes():
                        body.extend(piece)
                        if len(body)>32768:return None
            value=json.loads(body)
            if not isinstance(value,dict):return None
            callbacks=value.get('redirect_uris')
            methods=value.get('token_endpoint_auth_methods_supported',[value.get('token_endpoint_auth_method')])
            if value.get('client_id')!=client_id or 'none' not in methods or not isinstance(callbacks,list) or not 1<=len(callbacks)<=20:return None
            if client_id == CODEX_CLIENT_ID:
                if value.get('application_type') != 'native' or any(uri not in CODEX_CALLBACKS for uri in callbacks):
                    return None
                client_type = CodexNativeClient
            else:
                if any(not isinstance(uri,str) or not re.fullmatch(r'https://chatgpt\.com/[A-Za-z0-9_/-]{1,512}',uri) for uri in callbacks):
                    return None
                client_type = OAuthClientInformationFull
            registered=client_type(client_id=client_id,client_secret=None,redirect_uris=callbacks,
                token_endpoint_auth_method='none',grant_types=['authorization_code','refresh_token'],response_types=['code'],scope=' '.join(SCOPES))
            if len(self.client_cache)>=128:self.client_cache.pop(next(iter(self.client_cache)))
            self.client_cache[client_id]=(time.monotonic()+300,registered)
            return registered
        except (httpx.HTTPError,ValueError,TypeError):return None

    async def register_client(self, client_info):
        raise NotImplementedError("dynamic registration is disabled")

    async def authorize(self, client, params: AuthorizationParams) -> str:
        if params.resource != self.settings.resource:
            raise AuthorizeError(error="invalid_request", error_description="exact MCP resource is required")
        requested = params.scopes or ["memory:read"]
        if not set(requested).issubset(SCOPES) or "memory:read" not in requested:
            raise AuthorizeError(error="invalid_scope", error_description="supported explicit memory scopes required")
        nonce = secrets.token_urlsafe(32)
        self.repository.put_control("authorize", nonce, {"client_id":client.client_id,
            "params":params.model_dump(mode="json"), "expires_at":time.time()+LOGIN_WINDOW_SECONDS})
        return self.settings.issuer + "/connect/" + nonce

    def finish_authorize(self, nonce: str, account: str, approved: bool) -> str:
        pending = self.repository.consume_control("authorize", nonce)
        if pending is None:
            raise ValueError("authorization_expired_or_consumed")
        params = AuthorizationParams.model_validate(pending["params"])
        fields = {"state":params.state} if params.state is not None else {}
        fields['iss']=self.settings.issuer+'/'
        if not approved:
            fields.update({"error":"access_denied"})
        else:
            code = secrets.token_urlsafe(32)
            payload = {"code":"", "scopes":params.scopes or ["memory:read"], "expires_at":time.time()+90,
                "client_id":pending["client_id"], "code_challenge":params.code_challenge,
                "redirect_uri":str(params.redirect_uri), "redirect_uri_provided_explicitly":params.redirect_uri_provided_explicitly,
                "resource":params.resource, "subject":account}
            self.repository.put_control("code", code, payload)
            fields["code"] = code
        redirect = str(params.redirect_uri)
        return redirect + ("&" if "?" in redirect else "?") + urlencode(fields)

    async def load_authorization_code(self, client, authorization_code: str):
        value = self.repository.get_control("code", authorization_code)
        if not value or value["client_id"] != client.client_id:
            return None
        return AuthorizationCode.model_validate(value | {"code":authorization_code})

    async def exchange_authorization_code(self, client, authorization_code):
        value = self.repository.consume_control("code", authorization_code.code)
        if not value or value["client_id"] != client.client_id:
            raise TokenError(error="invalid_grant", error_description="code expired or already used")
        return self._issue(value["subject"], client.client_id, value["scopes"], value["resource"])

    def _issue(self, account, client_id, scopes, resource, grant_id=None):
        if resource != self.settings.resource:
            raise TokenError(error="invalid_target",error_description="wrong resource")
        grant_id = grant_id or secrets.token_urlsafe(32)
        grant = self.repository.get_control("grant", grant_id)
        if grant is not None and grant.get("revoked"):
            raise TokenError(error="invalid_grant",error_description="grant revoked")
        if grant is None:
            self.repository.put_control("grant", grant_id, {"subject":account,"client_id":client_id,"revoked":False,"expires_at":time.time()+86400})
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        shared = {"client_id":client_id,"subject":account,"scopes":scopes,"resource":resource,"grant_id":grant_id}
        self.repository.put_control("access", access, shared | {"expires_at":int(time.time())+600})
        self.repository.put_control("refresh", refresh, shared | {"expires_at":int(time.time())+86400})
        return OAuthToken(access_token=access,token_type="Bearer",expires_in=600,refresh_token=refresh,scope=" ".join(scopes))

    async def load_access_token(self, token: str):
        value = self.repository.get_control("access",token)
        if not value or value["resource"] != self.settings.resource or not self.settings.permits_account(value["subject"]):
            return None
        grant = self.repository.get_control("grant",value["grant_id"])
        if not grant or grant["revoked"]:
            return None
        return AccessToken(token=token,client_id=value["client_id"],subject=value["subject"],scopes=value["scopes"],
            expires_at=value["expires_at"],resource=value["resource"],claims={"iss":self.settings.issuer})

    async def load_refresh_token(self,client,refresh_token):
        value=self.repository.get_control("refresh",refresh_token)
        if not value or value["client_id"]!=client.client_id:
            return None
        grant=self.repository.get_control("grant",value["grant_id"])
        if not grant or grant["revoked"]:
            return None
        return RefreshToken(token=refresh_token,client_id=client.client_id,subject=value["subject"],scopes=value["scopes"],
                            resource=value["resource"],expires_at=value["expires_at"])

    async def exchange_refresh_token(self,client,refresh_token,scopes):
        value=self.repository.consume_control("refresh",refresh_token.token)
        if not value or not set(scopes).issubset(value["scopes"]):
            raise TokenError(error="invalid_grant",error_description="refresh expired, replayed or escalated")
        try:
            await self.identity.revalidate(value['subject'])
        except ValueError:
            raise TokenError(error='invalid_grant',error_description='Firebase sign-in required again') from None
        return self._issue(value["subject"],client.client_id,scopes,value["resource"],value["grant_id"])

    async def revoke_token(self,token):
        value=self.repository.get_control("access",token.token) or self.repository.get_control("refresh",token.token)
        if value:
            grant=self.repository.get_control("grant",value["grant_id"])
            if grant:
                self.repository.put_control("grant",value["grant_id"],grant|{"revoked":True})
