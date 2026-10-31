"""Google OAuth 2.0 web flow endpoints."""

import hmac
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request

router = APIRouter()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
]

_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _get_allowed_emails() -> set[str]:
    """Return the set of lowercased email addresses permitted to sign in."""
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _build_flow(state: str | None = None) -> Flow:
    """Create and configure the Google OAuth 2.0 Flow instance."""
    flow = Flow.from_client_secrets_file(
        os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    return flow


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    """Initiate the Google OAuth 2.0 authorization flow."""
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    request.session["oauth_state"] = state
    return RedirectResponse(authorization_url)


@router.get("/callback")
def callback(request: Request) -> RedirectResponse:
    """Handle the OAuth 2.0 callback, enforce state and email allowlist, and persist token."""
    allowed_emails = _get_allowed_emails()
    if not allowed_emails:
        raise HTTPException(status_code=500, detail="ALLOWED_EMAILS not configured")

    # Enforce non-null CSRF state check against session state
    state = request.session.pop("oauth_state", None)
    query_state = request.query_params.get("state")
    if not state or not query_state or not hmac.compare_digest(str(state), query_state):
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state")

    flow = _build_flow(state=str(state))
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    scheme = redirect_uri.split("://")[0]
    callback_url = str(request.url).replace("http://", f"{scheme}://", 1)
    flow.fetch_token(authorization_response=callback_url)
    creds = flow.credentials

    # Verify the authenticated Google user's email against the allowlist before saving token
    if not creds or not creds.token:
        raise HTTPException(status_code=401, detail="Failed to obtain OAuth access token")

    resp = httpx.get(
        _USERINFO_URL,
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to verify Google user identity")

    userinfo = resp.json()
    email = str(userinfo.get("email", "")).strip().lower()
    email_verified = bool(userinfo.get("email_verified"))
    if not email_verified or not email or email not in allowed_emails:
        request.session.clear()
        raise HTTPException(status_code=403, detail="Unauthorized email address")

    token_path = Path(os.environ.get("GOOGLE_TOKEN_PATH", "token.json"))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    request.session["authenticated"] = True
    return RedirectResponse("/")
