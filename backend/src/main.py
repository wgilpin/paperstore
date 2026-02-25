"""FastAPI application entry point."""

import pathlib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.db import create_tables
from src.schemas.paper import ErrorResponse

app = FastAPI(title="PaperStore")

# Allow the Chrome extension (chrome-extension://*) and local dev front end.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production; prototype uses wildcard.
    allow_methods=["*"],
    allow_headers=["*"],
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
from src.api import papers  # noqa: E402

app.include_router(papers.router, prefix="/papers", tags=["papers"])

# Serve the frontend if it exists (built later in the project).
_frontend_dir = pathlib.Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
