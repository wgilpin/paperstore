"""arXiv metadata client."""

import re

import arxiv

from src.services.types import PaperMetadata

# arXiv's edge (Fastly) rate-limits the arxiv library's default UA aggressively.
# A descriptive UA with contact info is accepted. See arXiv API Terms of Use.
_USER_AGENT = "PaperStoreApp/1.0 (+https://github.com/wgilpin/paperstore; contact: wgilpin@gmail.com)"

# Matches new-style IDs like 2301.00001 (with optional version suffix).
_NEW_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")
# Matches legacy IDs like hep-th/9901001.
_LEGACY_ID_RE = re.compile(r"([\w-]+/\d{7})(?:v\d+)?")


def extract_arxiv_id(url_or_id: str) -> str:
    """Extract a normalised arXiv ID from any URL form or bare ID string.

    Raises ValueError if no arXiv ID can be found.
    """
    for pattern in (_NEW_ID_RE, _LEGACY_ID_RE):
        m = pattern.search(url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract arXiv ID from: {url_or_id!r}")


class ArxivUnavailableError(RuntimeError):
    """Raised when the arXiv API is unreachable or rate-limiting us."""


def get_arxiv_client() -> arxiv.Client:
    """Return a pre-configured arxiv.Client with proper User-Agent header overriding.

    This works around a bug in all versions of the arxiv library where the client's
    internal __try_parse_feed method hardcodes a request-level "user-agent" header,
    overriding any session-level default headers.
    """
    client = arxiv.Client()
    original_request = client._session.request

    def custom_request(method, url, *args, **kwargs):
        headers = kwargs.get("headers") or {}
        # Match case-insensitive user-agent values starting with 'arxiv.py/'
        ua = headers.get("user-agent") or headers.get("User-Agent")
        if ua and (ua.startswith("arxiv.py/") or ua == "arxiv.py/2.3.2"):
            headers["user-agent"] = _USER_AGENT
        kwargs["headers"] = headers
        return original_request(method, url, *args, **kwargs)

    client._session.request = custom_request
    return client


class ArxivClient:
    """Thin wrapper around the arxiv package."""

    def fetch(self, arxiv_id_or_url: str) -> PaperMetadata:
        """Fetch metadata for a paper by arXiv ID or URL.

        Raises ValueError if the paper is not found.
        """
        arxiv_id = extract_arxiv_id(arxiv_id_or_url)
        search = arxiv.Search(id_list=[arxiv_id])
        client = get_arxiv_client()
        try:
            results = list(client.results(search))
        except arxiv.HTTPError as exc:
            raise ArxivUnavailableError(
                f"arXiv API request failed (HTTP {exc.status}): {arxiv_id}"
            ) from exc
        if not results:
            raise ValueError(f"arXiv paper not found: {arxiv_id!r}")
        result = results[0]
        authors = [a.name for a in result.authors]
        published_date = result.published.date() if result.published else None
        return PaperMetadata(
            title=result.title,
            authors=authors,
            published_date=published_date,
            abstract=result.summary,
            arxiv_id=arxiv_id,
        )

