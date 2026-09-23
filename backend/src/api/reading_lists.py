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


@router.get("", response_class=HTMLResponse)
def lists_index(request: Request, db: Session = Depends(get_session)) -> HTMLResponse:
    """Show every reading list, newest first, with its progress."""
    summaries = ReadingListService().list_summaries(db)
    return templates.TemplateResponse(request, "lists/index.html", {"summaries": summaries})


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
    service = ReadingListService()
    reading_list = service.get_list(list_id, db)
    return templates.TemplateResponse(
        request,
        "lists/detail.html",
        {"reading_list": reading_list, "progress": service.progress(reading_list)},
    )


@router.post("/{list_id}/items/{item_id}/tick", response_class=HTMLResponse)
def tick_item(
    request: Request,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Toggle an item's tick; return the item and, out of band, the progress line."""
    service = ReadingListService()
    item = service.toggle_tick(list_id, item_id, db)
    progress = service.progress(service.get_list(list_id, db))
    return templates.TemplateResponse(
        request, "lists/_tick.html", {"item": item, "progress": progress}
    )


@router.delete("/{list_id}/items/{item_id}", response_class=HTMLResponse)
def drop_item(
    request: Request,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Drop an item; the empty body removes it, and the progress line updates out of band."""
    service = ReadingListService()
    service.drop_item(list_id, item_id, db)
    progress = service.progress(service.get_list(list_id, db))
    return templates.TemplateResponse(request, "lists/_drop.html", {"progress": progress})


@router.delete("/{list_id}")
def delete_list(list_id: uuid.UUID, db: Session = Depends(get_session)) -> Response:
    """Delete a list and its items, then send the browser to the lists index."""
    ReadingListService().delete_list(list_id, db)
    return Response(status_code=204, headers={"HX-Redirect": "/lists"})


@router.post("/{list_id}/parse")
def parse_list_again(
    request: Request, list_id: uuid.UUID, db: Session = Depends(get_session)
) -> Response:
    """Parse a list's saved raw text again, then reload its page."""
    service = ReadingListService()
    reading_list = service.get_list(list_id, db)
    items = ReadingListParser().parse(reading_list.raw_text)
    service.parse_again(list_id, items, db)
    return _redirect(request, f"/lists/{list_id}")
