"""Reading lists router — server-rendered pages driven by HTMX.

Mounted at /lists, not under /api/, because AuthMiddleware exempts /api/.
"""

import logging
import pathlib
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import Response

from src.db import get_session
from src.services.reading_list_parser import ReadingListParser
from src.services.reading_lists import ReadingListService, safe_url, start_import, start_lookup

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(pathlib.Path(__file__).parent.parent / "templates"))

# Templates render an item's link only when it is http(s).
templates.env.globals["safe_url"] = safe_url

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
    if items:
        start_lookup(reading_list.id)
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
        {
            "reading_list": reading_list,
            "progress": service.progress(reading_list),
            "status": service.lookup_status(reading_list),
            "list_id": reading_list.id,
        },
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


@router.post("/{list_id}/name")
def rename_list(
    request: Request,
    list_id: uuid.UUID,
    name: str = Form(...),
    db: Session = Depends(get_session),
) -> Response:
    """Rename a list, then reload its page."""
    ReadingListService().rename_list(list_id, name, db)
    return _redirect(request, f"/lists/{list_id}")


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
    if items:
        start_lookup(list_id)
    return _redirect(request, f"/lists/{list_id}")


# Labels for lookup outcomes on the review page.
_OUTCOME_LABELS = {
    "in_library": "In your library",
    "free_pdf": "Free PDF",
    "record_only": "Record only, no free PDF",
    "not_found": "Not found",
}


@router.post("/{list_id}/find")
def find_papers(
    request: Request, list_id: uuid.UUID, db: Session = Depends(get_session)
) -> Response:
    """Start the background lookup of the list's unlinked items, and reload the list."""
    ReadingListService().get_list(list_id, db)  # 404 for an unknown list
    start_lookup(list_id)
    return _redirect(request, f"/lists/{list_id}")


@router.get("/{list_id}/lookup-status", response_class=HTMLResponse)
def lookup_status(
    request: Request, list_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """The list page's lookup controls; polled every 2 seconds while a lookup runs."""
    service = ReadingListService()
    reading_list = service.get_list(list_id, db)
    status = service.lookup_status(reading_list)
    if not status.running and not status.importing:
        # The poll that sees the work finish reloads the page, so the items update.
        return HTMLResponse("", headers={"HX-Refresh": "true"})
    return templates.TemplateResponse(
        request, "lists/_lookup_status.html", {"status": status, "list_id": list_id}
    )


@router.get("/{list_id}/review", response_class=HTMLResponse)
def review_page(
    request: Request, list_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """Show each looked-up item with its match, for Will to accept or reject."""
    service = ReadingListService()
    reading_list = service.get_list(list_id, db)
    return templates.TemplateResponse(
        request,
        "lists/review.html",
        {
            "reading_list": reading_list,
            "items": service.review_items(reading_list),
            "outcome_labels": _OUTCOME_LABELS,
        },
    )


@router.post("/{list_id}/review")
def submit_review(
    list_id: uuid.UUID,
    accept: list[uuid.UUID] = Form(default=[]),
    db: Session = Depends(get_session),
) -> Response:
    """Apply the accepted matches, start importing free PDFs, and go back to the list."""
    start_import(ReadingListService().apply_review(list_id, set(accept), db))
    return RedirectResponse(f"/lists/{list_id}", status_code=303)


@router.post("/{list_id}/items/{item_id}/upload", response_class=HTMLResponse)
def upload_item_pdf(
    request: Request,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Ingest an uploaded PDF for an item and link it; show any error in the item row."""
    service = ReadingListService()
    error: str | None = None
    try:
        service.upload_pdf(list_id, item_id, file.file.read(), file.filename or "upload.pdf", db)
    except ValueError as exc:
        error = str(exc)
    except Exception:
        db.rollback()
        logger.exception("PDF upload failed for reading list item %s", item_id)
        error = "The upload failed. Try again."
    item = service.get_item(list_id, item_id, db)
    return templates.TemplateResponse(request, "lists/_item.html", {"item": item, "error": error})


@router.post("/{list_id}/items/{item_id}/link", response_class=HTMLResponse)
def add_item_link(
    request: Request,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    url: str = Form(...),
    db: Session = Depends(get_session),
) -> HTMLResponse:
    """Give an item a URL: import a paper URL, keep any other link; show errors in the row."""
    service = ReadingListService()
    error: str | None = None
    try:
        start_import(service.add_url(list_id, item_id, url, db))
    except ValueError as exc:
        error = str(exc)
    item = service.get_item(list_id, item_id, db)
    # The status block comes back out of band, so it polls while the import runs.
    return templates.TemplateResponse(
        request,
        "lists/_item_and_status.html",
        {
            "item": item,
            "error": error,
            "status": service.lookup_status(service.get_list(list_id, db)),
            "list_id": list_id,
        },
    )


def _item_and_status(
    request: Request,
    service: ReadingListService,
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    error: str | None,
    db: Session,
) -> HTMLResponse:
    """The item row, plus the status block and progress line out of band."""
    reading_list = service.get_list(list_id, db)
    return templates.TemplateResponse(
        request,
        "lists/_item_and_status.html",
        {
            "item": service.get_item(list_id, item_id, db),
            "error": error,
            "status": service.lookup_status(reading_list),
            "progress": service.progress(reading_list),
            "list_id": list_id,
        },
    )


@router.post("/{list_id}/items/{item_id}/search", response_class=HTMLResponse)
def search_item_again(
    request: Request, list_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """Send one item back through lookup."""
    service = ReadingListService()
    error: str | None = None
    try:
        service.search_again(list_id, item_id, db)
        start_lookup(list_id)
    except ValueError as exc:
        error = str(exc)
    return _item_and_status(request, service, list_id, item_id, error, db)


@router.post("/{list_id}/items/{item_id}/unlink", response_class=HTMLResponse)
def unlink_item(
    request: Request, list_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """Remove an item's paper link; the paper stays in the library."""
    service = ReadingListService()
    error: str | None = None
    try:
        service.unlink(list_id, item_id, db)
    except ValueError as exc:
        error = str(exc)
    return _item_and_status(request, service, list_id, item_id, error, db)


@router.post("/{list_id}/items/{item_id}/retry", response_class=HTMLResponse)
def retry_item_import(
    request: Request, list_id: uuid.UUID, item_id: uuid.UUID, db: Session = Depends(get_session)
) -> HTMLResponse:
    """Run a failed import again."""
    service = ReadingListService()
    error: str | None = None
    try:
        start_import(service.retry_import(list_id, item_id, db))
    except ValueError as exc:
        error = str(exc)
    return _item_and_status(request, service, list_id, item_id, error, db)
