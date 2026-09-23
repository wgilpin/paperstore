"""Reading lists router — server-rendered pages driven by HTMX.

Mounted at /lists, not under /api/, because AuthMiddleware exempts /api/.
"""

import pathlib
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import Response

from src.db import get_session
from src.services.reading_list_parser import ReadingListParser
from src.services.reading_lists import ReadingListService

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent.parent / "templates"))

router = APIRouter()


def _redirect(request: Request, url: str) -> Response:
    """Redirect an HTMX request with HX-Redirect, and a plain form post with a 303."""
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


@router.get("/new", response_class=HTMLResponse)
def new_list_form(request: Request) -> HTMLResponse:
    """Show the paste form for a new reading list."""
    return templates.TemplateResponse(request, "lists/new.html", {})


@router.post("")
def create_list(
    request: Request,
    name: str = Form(...),
    raw_text: str = Form(...),
    db: Session = Depends(get_session),
) -> Response:
    """Parse the pasted list with Gemini, save it, and go to its page."""
    items = ReadingListParser().parse(raw_text)
    reading_list = ReadingListService().create_list(
        name.strip() or "Untitled list", raw_text, items, db
    )
    return _redirect(request, f"/lists/{reading_list.id}")


@router.get("/{list_id}", response_class=HTMLResponse)
def list_detail(
    request: Request, list_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """Show one reading list with its items in order."""
    reading_list = ReadingListService().get_list(list_id, db)
    return templates.TemplateResponse(request, "lists/detail.html", {"reading_list": reading_list})
