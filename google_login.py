"""Google OpenID Connect authorization-code flow, verified by Authlib."""
import json,os,secrets
from pathlib import Path
from flask import session,redirect,request,g,jsonify
from authlib.integrations.flask_client import OAuth
from access import OWNER_EMAIL

def register(a):
    config_path=a.ROOT/'google-auth.local.json'
    config=json.loads(config_path.read_text()) if config_path.exists() else {}
    client_id=os.environ.get('GOOGLE_CLIENT_ID',config.get('client_id',''))
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET',config.get('client_secret',''))
    callback=os.environ.get('GOOGLE_REDIRECT_URI',config.get('redirect_uri','http://127.0.0.1:5055/auth/google/callback'))
    ready=bool(client_id and client_secret)
    a.app.config['GOOGLE_READY']=ready
    oauth=OAuth(a.app)
    google=oauth.register(name='google',client_id=client_id,client_secret=client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope':'openid email profile','code_challenge_method':'S256'})
    a.app.extensions['inventory_google']=google

    @a.app.get('/auth/google')
    def google_start():
        if not a.app.config['GOOGLE_READY']: return redirect('/?login_error=google_not_configured')
        return google.authorize_redirect(callback,login_hint=OWNER_EMAIL,prompt='select_account')

    @a.app.get('/auth/google/callback')
    def google_callback():
        if not a.app.config['GOOGLE_READY']: return redirect('/?login_error=google_not_configured')
        try:
            # Authlib verifies state, signature/JWKS, issuer, audience, expiry and nonce.
            token=google.authorize_access_token()
            claims=token.get('userinfo')
            if not claims or claims.get('email_verified') is not True or not claims.get('sub'): return redirect('/?login_error=google_denied')
            email=str(claims.get('email','')).strip().lower()
            a.db().execute('BEGIN IMMEDIATE')
            u=a.one('SELECT * FROM users WHERE username=? AND active=1',(email,))
            if not u or email!=OWNER_EMAIL: return redirect('/?login_error=google_denied')
            if u['google_sub'] and u['google_sub']!=claims['sub']: return redirect('/?login_error=google_denied')
            if not u['google_sub']: a.db().execute('UPDATE users SET google_sub=? WHERE id=?',(claims['sub'],u['id']))
            g.user=u;a.audit('GOOGLE_LOGIN',{'user_id':u['id']});a.db().commit()
            session.clear();session['uid']=u['id'];session['auth_version']=u['auth_version'];session['csrf']=secrets.token_hex(24);session.permanent=True
            return redirect('/')
        except Exception:
            # Never expose authorization codes, tokens, provider responses or credentials in logs.
            a.app.logger.warning('Google sign-in failed validation or provider connection')
            return redirect('/?login_error=google_failed')
