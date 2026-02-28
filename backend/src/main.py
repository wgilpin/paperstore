"""FastAPI application entry point."""

import logging
import os
import pathlib
from collections.abc import Awaitable, Callable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")

# Apply the same format to Uvicorn's loggers so they also show timestamps.
for _uvicorn_logger in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _log = logging.getLogger(_uvicorn_logger)
    _log.handlers.clear()
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    _log.addHandler(_handler)
    _log.propagate = False

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from starlette.responses import Response

from src.db import create_tables
from src.schemas.paper import ErrorResponse

app = FastAPI(title="PaperStore")

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Allow the Chrome extension (chrome-extension://*) and local dev front end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production; prototype uses wildcard.
    allow_methods=["*"],
    allow_headers=["*"],
)

_AUTH_EXEMPT_PREFIXES = ("/auth/",)


def _load_credentials() -> bool:
    """Return True if a valid (or refreshable) token exists."""
    import os
    from pathlib import Path

    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.credentials import Credentials

    token_path = Path(os.environ.get("GOOGLE_TOKEN_PATH", "token.json"))
    if not token_path.exists():
        return False
    try:
        creds: Credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_path)
        )
        if creds.valid:
            return True
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            token_path.write_text(creds.to_json())  # type: ignore[no-untyped-call]
            return True
    except Exception:
        pass
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if any(request.url.path.startswith(p) for p in _AUTH_EXEMPT_PREFIXES):
            return await call_next(request)
        if not request.session.get("authenticated"):
            return RedirectResponse("/auth/login")
        return await call_next(request)


# SessionMiddleware must wrap AuthMiddleware (added after so it runs first).
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-me"),
)


@app.on_event("startup")
def startup() -> None:
    create_tables()


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Import here to avoid circular imports at module level.
    from src.services.drive import DriveUploadError
    from src.services.ingestion import DuplicateError
    from src.services.notes import NotFoundError

    if isinstance(exc, DuplicateError):
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(error="duplicate", detail=str(exc)).model_dump(),
        )
    if isinstance(exc, NotFoundError):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(error="not_found", detail=str(exc)).model_dump(),
        )
    if isinstance(exc, DriveUploadError):
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(error="drive_upload_error", detail=str(exc)).model_dump(),
        )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="internal_error", detail=str(exc)).model_dump(),
    )


# Import and register routers after app is defined to avoid circular imports.
from src.api import auth, batch, papers, tags  # noqa: E402

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(papers.router, prefix="/papers", tags=["papers"])
app.include_router(tags.router, prefix="/tags", tags=["tags"])
app.include_router(batch.router, prefix="/batch", tags=["batch"])

# Serve the frontend if it exists (built later in the project).
_frontend_dir = pathlib.Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
