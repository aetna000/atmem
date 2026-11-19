"""User account journeys against real Firebase Auth and Firestore emulators."""
import json
import secrets

import httpx

from .conftest import csrf


def test_standalone_signup_verify_login_recovery_and_logout(cloud):
    from atmem.chatgpt.config import Settings
    from atmem.chatgpt.repository import Repository
    original=cloud.config.read_text()
    config=json.loads(original);config['access_policy']='registered'
    cloud.config.write_text(json.dumps(config));cloud.restart()
    browser=httpx.Client(timeout=20)
    email='account-'+secrets.token_hex(8)+'@example.invalid'
    password=secrets.token_urlsafe(24)
    auth='http://'+cloud.env['FIREBASE_AUTH_EMULATOR_HOST']
    repo=Repository(Settings.load(cloud.config))
    def post(path,**data):
        form=browser.get(cloud.base+path)
        return browser.post(cloud.base+path,headers={'Origin':cloud.base},data={'csrf':csrf(form),**data})
    def codes(kind):
        rows=httpx.get(auth+'/emulator/v1/projects/demo-atmem-plugin/oobCodes').json()['oobCodes']
        return [row for row in rows if row['email']==email and row['requestType']==kind]
    try:
        assert browser.get(cloud.base+'/').headers['location']==cloud.base+'/login'
        for path in ['/login','/register','/verify-email','/reset-password']:
            assert browser.get(cloud.base+path).status_code==200
        assert browser.get(cloud.base+'/register?request=forged').status_code==400
        form=browser.get(cloud.base+'/register')
        # Another tab must not invalidate the original form's CSRF token.
        browser.get(cloud.base+'/reset-password')
        created=browser.post(cloud.base+'/register',headers={'Origin':cloud.base},data={'csrf':csrf(form),'email':email,'password':password,'understood':'yes'})
        assert created.status_code==200 and 'Check your email' in created.text
        unverified=post('/login',email=email,password=password)
        assert unverified.status_code==403 and 'Resend verification' in unverified.text
        # No human session/identity is issued to an unverified account.
        import base64
        cookie=browser.cookies.get('atmem_human').split('.')[0]
        assert 'human_session' not in json.loads(base64.b64decode(cookie))
        repo._doc('email-limit',email).delete()  # Only our synthetic emulator address.
        resent=post('/verify-email',email=email,password=password)
        assert resent.status_code==200
        verified=httpx.post(auth+'/identitytoolkit.googleapis.com/v1/accounts:update',params={'key':'emulator'},json={'oobCode':codes('VERIFY_EMAIL')[-1]['oobCode']})
        assert verified.status_code==200
        rejected=post('/login',email=email,password='wrong-password')
        assert rejected.status_code==403 and 'Reset password' in rejected.text
        accepted=post('/login',email=email,password=password)
        assert accepted.status_code==200 and 'Signed in to AtMem' in accepted.text
        # Explicit wrong credentials cannot silently reuse a signed-in browser.
        assert post('/login',email=email,password='wrong-again').status_code==403
        form=browser.get(cloud.base+'/login')
        assert browser.post(cloud.base+'/logout',headers={'Origin':'https://attacker.invalid'},data={'csrf':csrf(form)}).status_code==403
        # Sign in again to obtain the logout form and revoke only this session.
        accepted=post('/login',email=email,password=password)
        signed_out=browser.post(cloud.base+'/logout',headers={'Origin':cloud.base},data={'csrf':csrf(accepted)})
        assert signed_out.status_code==200 and 'Signed out' in signed_out.text
        cookie=browser.cookies.get('atmem_human')
        assert not cookie
        repo._doc('email-limit',email).delete()
        recovered=post('/reset-password',email=email)
        assert recovered.status_code==200
        new_password=secrets.token_urlsafe(24)
        reset=httpx.post(auth+'/identitytoolkit.googleapis.com/v1/accounts:resetPassword',params={'key':'emulator'},json={'oobCode':codes('PASSWORD_RESET')[-1]['oobCode'],'newPassword':new_password})
        assert reset.status_code==200
        assert post('/login',email=email,password=password).status_code==403
        assert post('/login',email=email,password=new_password).status_code==200
        import subprocess
        from pathlib import Path
        result=subprocess.run(['node',str(Path(__file__).parent/'browser/account-access.mjs')],input=json.dumps({'base':cloud.base,'email':email,'password':new_password}),capture_output=True,text=True,timeout=60)
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)['loginRecoveryLogout']
        stale=browser.get(cloud.base+'/connect/'+'x'*32)
        assert stale.status_code==400 and 'href="/register"' in stale.text
        # Caller-supplied next URLs are ignored, never used as redirects.
        response=browser.get(cloud.base+'/login?next=https://attacker.invalid')
        assert response.status_code==200 and 'location' not in response.headers
        assert browser.post(cloud.base+'/login',headers={'Origin':cloud.base},data={'email':email,'password':new_password}).status_code==403
    finally:
        browser.close();cloud.config.write_text(original);cloud.restart()
