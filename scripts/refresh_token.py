#!/usr/bin/env python3
"""Re-authorize Google OAuth token (YouTube Data API).

Use when the refresh token goes stale (invalid_grant error):
  1. Start this script (runs local server on port 5678)
  2. Open the printed AUTH_URL in your browser
  3. Approve the scopes
  4. Script saves the new token to ~/.hermes/google_token.json

Usage:
  python3 refresh_token.py
"""
import json, threading, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import Flow

CLIENT_SECRET = "/home/sylvain/.hermes/google_client_secret.json"
TOKEN_PATH = "/home/sylvain/.hermes/google_token.json"

with open(CLIENT_SECRET) as f:
    cc = json.load(f)["web"]
with open(TOKEN_PATH) as f:
    existing = json.load(f)

REDIRECT_URI = "http://localhost:5678/rest/oauth2-credential/callback"
scopes = list(dict.fromkeys(existing.get("scopes", []) + ["https://www.googleapis.com/auth/youtube.readonly"]))

flow = Flow.from_client_secrets_file(CLIENT_SECRET, scopes=scopes, redirect_uri=REDIRECT_URI)
auth_url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')

code = [None]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        c = qs.get("code", [None])[0]
        if c:
            code[0] = c
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>OK, you can close this tab</h1>")
        else:
            self.send_response(400)
            self.end_headers()
    def log_message(self, *a): pass

server = HTTPServer(("localhost", 5678), Handler)
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()
print("SERVER_READY")
print(f"AUTH_URL:{auth_url}")
sys.stdout.flush()

for _ in range(300):
    if code[0]: break
    time.sleep(1)
else:
    print("TIMEOUT")
    exit(1)

server.shutdown()
print("CODE_OK")
sys.stdout.flush()

flow.fetch_token(code=code[0])
creds = flow.credentials

new_token = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": list(creds.scopes),
    "universe_domain": "googleapis.com",
    "account": "",
    "expiry": creds.expiry.isoformat(),
    "type": "authorized_user"
}

with open(TOKEN_PATH, "w") as f:
    json.dump(new_token, f, indent=2)

print("TOKEN_SAVED")
