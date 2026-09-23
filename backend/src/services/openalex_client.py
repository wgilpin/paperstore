"""OpenAlex client — title search over scholarly works (free, no API key)."""

import logging

import httpx
from pydantic import BaseModel

from src.services.arxiv_client import extract_arxiv_id

logger = logging.getLogger(__name__)

_URL = "https://api.openalex.org/works"


class OpenAlexWork(BaseModel):
    """The parts of an OpenAlex work that citation lookup uses."""

    title: str
    year: int | None
    authors: list[str]
    # Bare DOI, lower case, without the https://doi.org/ prefix.
    doi: str | None
    # OpenAlex work type, for example "article", "book", "book-review", "paratext".
    type: str | None
    pdf_urls: list[str]
    arxiv_id: str | None
    landing_url: str | None


def _arxiv_id_from(url: str | None) -> str | None:
    if not url or "arxiv.org" not in url:
        return None
    try:
        return extract_arxiv_id(url)
    except ValueError:
        return None


def _parse(raw: dict[str, object]) -> OpenAlexWork | None:
    """Turn one OpenAlex result into an OpenAlexWork; None when it has no title."""
    title = raw.get("display_name")
    if not isinstance(title, str) or not title:
        return None
    doi_raw = raw.get("doi")
    doi = doi_raw.lower().removeprefix("https://doi.org/") if isinstance(doi_raw, str) else None
    authors: list[str] = []
    for authorship in raw.get("authorships") or []:  # type: ignore[attr-defined]
        name = ((authorship or {}).get("author") or {}).get("display_name")
        if isinstance(name, str):
            authors.append(name)
    pdf_urls: list[str] = []
    arxiv_id: str | None = None
    landing_url: str | None = None
    for loc in raw.get("locations") or []:  # type: ignore[attr-defined]
        if not isinstance(loc, dict):
            continue
        landing = loc.get("landing_page_url")
        pdf = loc.get("pdf_url")
        if isinstance(pdf, str) and pdf not in pdf_urls:
            pdf_urls.append(pdf)
        arxiv_id = arxiv_id or _arxiv_id_from(landing if isinstance(landing, str) else None)
        if landing_url is None and isinstance(landing, str):
            landing_url = landing
    year = raw.get("publication_year")
    work_type = raw.get("type")
    return OpenAlexWork(
        title=title,
        year=year if isinstance(year, int) else None,
        authors=authors,
        doi=doi,
        type=work_type if isinstance(work_type, str) else None,
        pdf_urls=pdf_urls,
        arxiv_id=arxiv_id,
        landing_url=landing_url or (f"https://doi.org/{doi}" if doi else None),
    )


class OpenAlexClient:
    def search(self, title: str) -> list[OpenAlexWork]:
        """Return up to five works whose text matches *title*; [] on any error."""
        try:
            response = httpx.get(_URL, params={"search": title, "per-page": 5}, timeout=20)
            response.raise_for_status()
            results = response.json().get("results") or []
        except Exception as exc:
            logger.warning("OpenAlex search failed for %r: %s", title, exc)
            return []
        works = [_parse(r) for r in results if isinstance(r, dict)]
        return [w for w in works if w is not None]
