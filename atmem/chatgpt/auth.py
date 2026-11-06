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
import time
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import AuthorizationCode, AuthorizationParams, AccessToken, RefreshToken, AuthorizeError, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .config import Settings, SCOPES
from .repository import Repository


class FirebaseIdentity:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def sign_in(self, email: str, password: str) -> str:
        if not 3 <= len(email) <= 254 or not 1 <= len(password) <= 256:
            raise ValueError("sign_in_rejected")
        if self.settings.emulator:
            import os
            base = "http://" + os.environ["FIREBASE_AUTH_EMULATOR_HOST"] + "/identitytoolkit.googleapis.com/v1"
        else:
            base = "https://identitytoolkit.googleapis.com/v1"
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(base + "/accounts:signInWithPassword", params={"key":self.settings.firebase_api_key},
                json={"email":email,"password":password,"returnSecureToken":True})
        if response.status_code != 200:
            raise ValueError("sign_in_rejected")
        uid = response.json().get("localId")
        if not isinstance(uid, str) or not uid or len(uid)>128:
            raise ValueError("sign_in_rejected")
        # This ID token comes directly from Firebase over the configured HTTPS
        # sign-in response (or explicit loopback emulator), never from the caller.
        # Check its project/issuer binding so a wrong project's API key cannot
        # authenticate an identically named UID into this service. This is not
        # a general verifier for client-supplied Firebase JWTs.
        try:
            encoded=response.json()["idToken"].split(".")[1]
            claims=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
            if claims.get("aud")!=self.settings.project or claims.get("iss")!="https://securetoken.google.com/"+self.settings.project or claims.get("sub")!=uid or claims.get("exp",0)<=time.time():
                raise ValueError("identity_project_mismatch")
        except (KeyError,IndexError,TypeError,ValueError):
            raise ValueError("sign_in_rejected") from None
        if not self.settings.permits_account(uid):
            raise ValueError("account_not_invited")
        return uid


class OAuthProvider:
    def __init__(self, settings: Settings, repository: Repository):
        self.settings = settings; self.repository = repository

    async def get_client(self, client_id: str):
        callbacks = self.settings.clients.get(client_id)
        if callbacks is None:
            return None
        return OAuthClientInformationFull(client_id=client_id, client_secret=None,
            redirect_uris=list(callbacks), token_endpoint_auth_method="none",
            grant_types=["authorization_code","refresh_token"], response_types=["code"], scope=" ".join(SCOPES))

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
            "params":params.model_dump(mode="json"), "expires_at":time.time()+300})
        return self.settings.issuer + "/connect/" + nonce

    def finish_authorize(self, nonce: str, account: str, approved: bool) -> str:
        pending = self.repository.consume_control("authorize", nonce)
        if pending is None:
            raise ValueError("authorization_expired_or_consumed")
        params = AuthorizationParams.model_validate(pending["params"])
        fields = {"state":params.state} if params.state is not None else {}
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
        return self._issue(value["subject"],client.client_id,scopes,value["resource"],value["grant_id"])

    async def revoke_token(self,token):
        value=self.repository.get_control("access",token.token) or self.repository.get_control("refresh",token.token)
        if value:
            grant=self.repository.get_control("grant",value["grant_id"])
            if grant:
                self.repository.put_control("grant",value["grant_id"],grant|{"revoked":True})
