"""bioRxiv metadata client.

bioRxiv preprints are identified by a DOI. Metadata comes from the Crossref API,
which covers both the legacy 10.1101 prefix and the current openRxiv prefixes.
The PDF is downloaded from biorxiv.org itself.
"""

import re
from datetime import date
from html import unescape
from urllib.parse import urlparse

import httpx

from src.services.types import PaperMetadata

_CROSSREF_URL = "https://api.crossref.org/works/{doi}"
_USER_AGENT = "PaperStoreApp/1.0 (+https://github.com/wgilpin/paperstore; mailto:wgilpin@gmail.com)"

_BIORXIV_HOSTNAMES = {"biorxiv.org", "connect.biorxiv.org"}

# Matches the DOI and optional version in a bioRxiv content path, for example
# /content/10.64898/2026.02.12.705387v2 or /content/10.1101/2020.01.30.927871v1.full.pdf
_CONTENT_PATH_RE = re.compile(
    r"/content/(?P<doi>10\.\d{4,9}/[^/\s]+?)(?:v(?P<version>\d+))?(?:\.full(?:-text)?|\.full\.pdf|\.pdf)?/?$"
)
# Matches a bare DOI or a doi.org URL.
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s?#]+)")

_JATS_TAG_RE = re.compile(r"<[^>]+>")


class BiorxivUnavailableError(RuntimeError):
    """Raised when the Crossref API is unreachable or has no record for the DOI."""


def is_biorxiv_url(url: str) -> bool:
    """Return True if *url* points at a bioRxiv preprint page or PDF."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    return hostname in _BIORXIV_HOSTNAMES or hostname.endswith(".biorxiv.org")


def parse_biorxiv_url(url: str) -> tuple[str, str | None]:
    """Return (doi, version) for a bioRxiv URL or bare DOI.

    *version* is the version suffix without the leading "v", or None if absent.
    Raises ValueError if no DOI can be found.
    """
    parsed = urlparse(url)
    match = _CONTENT_PATH_RE.search(parsed.path)
    if match:
        return match.group("doi"), match.group("version")

    doi_match = _DOI_RE.search(url)
    if doi_match:
        doi = doi_match.group(1)
        version_match = re.search(r"v(\d+)$", doi)
        if version_match:
            doi = doi[: version_match.start()]
            return doi, version_match.group(1)
        return doi, None

    raise ValueError(f"Cannot extract bioRxiv DOI from: {url!r}")


def canonical_biorxiv_url(doi: str, version: str | None) -> str:
    """Return the canonical abstract-page URL, without tracking parameters."""
    suffix = f"v{version}" if version else ""
    return f"https://www.biorxiv.org/content/{doi}{suffix}"


def biorxiv_pdf_url(doi: str, version: str | None) -> str:
    """Return the full-text PDF URL for a bioRxiv preprint."""
    suffix = f"v{version}" if version else ""
    return f"https://www.biorxiv.org/content/{doi}{suffix}.full.pdf"


def _clean_abstract(raw: str | None) -> str | None:
    """Strip the JATS markup Crossref wraps abstracts in."""
    if not raw:
        return None
    text = _JATS_TAG_RE.sub("", raw)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower().startswith("abstract"):
        text = text[len("abstract") :].lstrip(" :.-")
    return text or None


class BiorxivClient:
    """Fetch bioRxiv preprint metadata from Crossref."""

    def fetch(self, url_or_doi: str) -> PaperMetadata:
        """Fetch metadata for a bioRxiv preprint by URL or DOI.

        Raises BiorxivUnavailableError if Crossref is unreachable or has no record.
        Raises ValueError if no DOI can be extracted from *url_or_doi*.
        """
        doi, _ = parse_biorxiv_url(url_or_doi)
        try:
            response = httpx.get(
                _CROSSREF_URL.format(doi=doi),
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                follow_redirects=True,
                timeout=30,
            )
            response.raise_for_status()
            message = response.json()["message"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise BiorxivUnavailableError(f"Crossref lookup failed for {doi}: {exc}") from exc

        titles = message.get("title") or []
        title = titles[0].strip() if titles else None

        authors: list[str] = []
        for author in message.get("author") or []:
            name = " ".join(
                part for part in (author.get("given"), author.get("family")) if part
            ).strip()
            if not name:
                name = (author.get("name") or "").strip()
            if name:
                authors.append(name)

        published_date: date | None = None
        date_parts = (message.get("posted") or message.get("issued") or {}).get("date-parts") or []
        if date_parts and len(date_parts[0]) == 3:
            year, month, day = date_parts[0]
            published_date = date(year, month, day)

        return PaperMetadata(
            title=title,
            authors=authors,
            published_date=published_date,
            abstract=_clean_abstract(message.get("abstract")),
            arxiv_id=None,
        )
