"""Google OAuth 2.0 web flow endpoints."""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from starlette.requests import Request

router = APIRouter()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/drive.file",
]


def _build_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_secrets_file(
        os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json"),
        scopes=SCOPES,
        state=state,
    )
    flow.redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    return flow


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    request.session["oauth_state"] = state
    return RedirectResponse(authorization_url)


@router.get("/callback")
def callback(request: Request) -> RedirectResponse:
    state = request.session.pop("oauth_state", None)
    flow = _build_flow(state=state)
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    scheme = redirect_uri.split("://")[0]
    callback_url = str(request.url).replace("http://", f"{scheme}://", 1)
    flow.fetch_token(authorization_response=callback_url)
    creds = flow.credentials
    token_path = Path(os.environ.get("GOOGLE_TOKEN_PATH", "token.json"))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    request.session["authenticated"] = True
    return RedirectResponse("/")
