"""arXiv metadata client."""

import re

import arxiv

from src.services.types import PaperMetadata

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


class ArxivClient:
    """Thin wrapper around the arxiv package."""

    def fetch(self, arxiv_id_or_url: str) -> PaperMetadata:
        """Fetch metadata for a paper by arXiv ID or URL.

        Raises ValueError if the paper is not found.
        """
        arxiv_id = extract_arxiv_id(arxiv_id_or_url)
        search = arxiv.Search(id_list=[arxiv_id])
        client = arxiv.Client()
        results = list(client.results(search))
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
