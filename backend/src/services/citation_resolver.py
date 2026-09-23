"""Citation resolver — finds the paper a reading-list citation refers to.

Sources are tried in order and each sits behind a small function, so tests can
replace them: the library (by arXiv ID, DOI, then title), then an arXiv ID written
in the citation, OpenAlex, and arXiv title search.
"""

import difflib
import logging
import re
import threading
import time

import arxiv
import httpx
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.reading_list import Candidate, ParsedItem
from src.services.arxiv_client import ArxivClient, extract_arxiv_id, get_arxiv_client
from src.services.openalex_client import OpenAlexClient, OpenAlexWork

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;]+)", re.IGNORECASE)
# pg_trgm similarity a library title must reach to be considered at all.
_LIBRARY_TITLE_SIMILARITY = 0.6
# Title agreement needed before the year or author check can make a match confident.
_TITLE_MATCH = 0.85
# OpenAlex work types that are never the cited work itself.
_REJECTED_TYPES = {"book-review", "paratext", "erratum", "retraction"}
# arXiv asks API clients to wait 3 seconds between calls.
_ARXIV_PAUSE_SECONDS = 3.0
_arxiv_lock = threading.Lock()
_arxiv_last_call = 0.0
_PDF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*;q=0.8",
    "Range": "bytes=0-1023",
}


class ArxivHit(BaseModel):
    """An arXiv record found by ID or by title search."""

    arxiv_id: str
    title: str
    authors: list[str]
    year: int | None


def _arxiv_pause() -> None:
    """Block until at least 3 seconds have passed since the last arXiv call."""
    global _arxiv_last_call
    with _arxiv_lock:
        wait = _ARXIV_PAUSE_SECONDS - (time.monotonic() - _arxiv_last_call)
        if wait > 0:
            time.sleep(wait)
        _arxiv_last_call = time.monotonic()


def library_by_arxiv_id(arxiv_id: str, db: Session) -> Paper | None:
    """Return the library paper with *arxiv_id*, if any."""
    return db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()


def library_by_doi(doi: str, db: Session) -> Paper | None:
    """Return the library paper with *doi* (case-insensitive), if any."""
    return db.query(Paper).filter(func.lower(Paper.doi) == doi.lower()).first()


def library_by_title(title: str, db: Session) -> list[Paper]:
    """Return library papers whose title is similar to *title*, best first (pg_trgm)."""
    similarity = func.similarity(Paper.title, title)
    return (
        db.query(Paper)
        .filter(similarity >= _LIBRARY_TITLE_SIMILARITY)
        .order_by(similarity.desc())
        .limit(5)
        .all()
    )


def arxiv_record(arxiv_id: str) -> ArxivHit | None:
    """Return the arXiv record for *arxiv_id*, or None if it is missing or arXiv fails."""
    _arxiv_pause()
    try:
        meta = ArxivClient().fetch(arxiv_id)
    except Exception as exc:
        logger.warning("arXiv lookup failed for %s: %s", arxiv_id, exc)
        return None
    published = meta["published_date"]
    return ArxivHit(
        arxiv_id=arxiv_id,
        title=meta["title"] or "",
        authors=meta["authors"],
        year=published.year if published else None,
    )


def arxiv_search(title: str) -> list[ArxivHit]:
    """Return up to five arXiv records whose titles contain the words of *title*."""
    words = [w for w in _norm(title).split() if len(w) > 2][:8]
    if not words:
        return []
    _arxiv_pause()
    search = arxiv.Search(query=" AND ".join(f"ti:{w}" for w in words), max_results=5)
    try:
        results = list(get_arxiv_client().results(search))
    except Exception as exc:
        logger.warning("arXiv search failed for %r: %s", title, exc)
        return []
    return [
        ArxivHit(
            arxiv_id=r.get_short_id().split("v")[0],
            title=" ".join(r.title.split()),
            authors=[a.name for a in r.authors],
            year=r.published.year if r.published else None,
        )
        for r in results
    ]


def openalex_search(title: str) -> list[OpenAlexWork]:
    """Return OpenAlex works for *title* (see OpenAlexClient.search)."""
    return OpenAlexClient().search(title)


def pdf_check(url: str) -> bool:
    """True when *url* serves a PDF to a plain request (fetches the first 1 KB only)."""
    try:
        with httpx.stream(
            "GET", url, headers=_PDF_HEADERS, follow_redirects=True, timeout=15
        ) as response:
            if response.status_code not in (200, 206):
                return False
            first = next(response.iter_bytes(), b"")
            return first.startswith(b"%PDF") or "pdf" in response.headers.get("content-type", "")
    except Exception:
        return False


def arxiv_id_in(citation: str) -> str | None:
    """Return an arXiv ID written in *citation*, if any."""
    try:
        return extract_arxiv_id(citation)
    except ValueError:
        return None


def doi_in(citation: str) -> str | None:
    """Return a DOI written in *citation*, if any, without trailing punctuation."""
    m = _DOI_RE.search(citation)
    return m.group(1).rstrip(".)") if m else None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower().replace("-", " ")).strip()


def title_similarity(cited: str, found: str) -> float:
    """Similarity in [0, 1]; a cited title that starts the found title counts as 0.9.

    The prefix rule covers citations that drop a subtitle.
    """
    a, b = _norm(cited), _norm(found)
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if a and b.startswith(a):
        ratio = max(ratio, 0.9)
    return ratio


def _surnames(names: list[str]) -> set[str]:
    """Last word of each name, normalised ("et al." dropped)."""
    out = set()
    for name in names:
        words = _norm(name.replace("et al", "")).split()
        if words:
            out.add(words[-1])
    return out


def is_confident(query: ParsedItem, title: str, authors: list[str], year: int | None) -> bool:
    """True when the title matches and the year (±1) or an author surname also agrees."""
    if title_similarity(query.title, title) < _TITLE_MATCH:
        return False
    year_ok = query.year is not None and year is not None and abs(query.year - year) <= 1
    authors_ok = bool(_surnames(query.authors) & _surnames(authors))
    return year_ok or authors_ok


def _library_candidate(paper: Paper, confident: bool) -> Candidate:
    return Candidate(
        source="library",
        title=paper.title,
        authors=list(paper.authors or []),
        year=paper.published_date.year if paper.published_date else None,
        arxiv_id=paper.arxiv_id,
        doi=paper.doi,
        paper_id=paper.id,
        confident=confident,
        outcome="in_library",
    )


def _arxiv_candidate(hit: ArxivHit, query: ParsedItem) -> Candidate:
    return Candidate(
        source="arxiv",
        title=hit.title,
        authors=hit.authors,
        year=hit.year,
        arxiv_id=hit.arxiv_id,
        pdf_url=f"https://arxiv.org/pdf/{hit.arxiv_id}",
        landing_url=f"https://arxiv.org/abs/{hit.arxiv_id}",
        confident=is_confident(query, hit.title, hit.authors, hit.year),
        outcome="free_pdf",
    )


def _best(query: ParsedItem, titles: list[str]) -> int | None:
    """Index of the title that matches *query* best, if any reaches the match threshold."""
    scored = [(title_similarity(query.title, t), i) for i, t in enumerate(titles)]
    good = [(score, i) for score, i in scored if score >= _TITLE_MATCH]
    return max(good)[1] if good else None


class CitationResolver:
    """Finds the best match for one citation."""

    def resolve(self, query: ParsedItem, db: Session) -> Candidate | None:
        """Return the best match for *query*, or None when nothing matches.

        A confident library match wins. Otherwise the outside sources are tried, and a
        weak library match is the fallback.
        """
        library = self._library(query, db)
        if library is not None and library.confident:
            return library
        return self._outside(query, db) or library

    def _outside(self, query: ParsedItem, db: Session) -> Candidate | None:
        """Look outside the library: cited arXiv ID, OpenAlex, then arXiv title search."""
        # 1. An arXiv ID written in the citation.
        arxiv_id = arxiv_id_in(query.citation)
        if arxiv_id:
            hit = arxiv_record(arxiv_id)
            if hit is not None:
                return _arxiv_candidate(hit, query)

        # 2. OpenAlex: the best title among works that can be the cited work.
        works = [w for w in openalex_search(query.title) if w.type not in _REJECTED_TYPES]
        best = _best(query, [w.title for w in works])
        if best is not None:
            return self._from_openalex(works[best], query, db)

        # 3. arXiv title search.
        hits = arxiv_search(query.title)
        best = _best(query, [h.title for h in hits])
        if best is not None:
            hit = hits[best]
            paper = library_by_arxiv_id(hit.arxiv_id, db)
            if paper is not None:
                return _library_candidate(
                    paper, is_confident(query, hit.title, hit.authors, hit.year)
                )
            return _arxiv_candidate(hit, query)
        return None

    def _from_openalex(self, work: OpenAlexWork, query: ParsedItem, db: Session) -> Candidate:
        """Turn a matching OpenAlex work into a candidate, preferring a library copy."""
        confident = is_confident(query, work.title, work.authors, work.year)
        paper = (library_by_arxiv_id(work.arxiv_id, db) if work.arxiv_id else None) or (
            library_by_doi(work.doi, db) if work.doi else None
        )
        if paper is not None:
            return _library_candidate(paper, confident)
        pdf_url = next((u for u in work.pdf_urls if pdf_check(u)), None)
        if pdf_url is None and work.arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{work.arxiv_id}"
        return Candidate(
            source="openalex",
            title=work.title,
            authors=work.authors,
            year=work.year,
            arxiv_id=work.arxiv_id,
            doi=work.doi,
            pdf_url=pdf_url,
            landing_url=work.landing_url,
            confident=confident,
            outcome="free_pdf" if pdf_url else "record_only",
        )

    def _library(self, query: ParsedItem, db: Session) -> Candidate | None:
        """Look in the library: by an ID in the citation, then by title."""
        # 1. Library by an ID written in the citation: exact, so confident.
        arxiv_id = arxiv_id_in(query.citation)
        if arxiv_id:
            paper = library_by_arxiv_id(arxiv_id, db)
            if paper:
                return _library_candidate(paper, confident=True)
        doi = doi_in(query.citation)
        if doi:
            paper = library_by_doi(doi, db)
            if paper:
                return _library_candidate(paper, confident=True)

        # 2. Library by title: take the best similar title that passes the match rule;
        #    otherwise offer the best one as a weak match.
        papers = library_by_title(query.title, db)
        for paper in papers:
            year = paper.published_date.year if paper.published_date else None
            if is_confident(query, paper.title, list(paper.authors or []), year):
                return _library_candidate(paper, confident=True)
        if papers:
            return _library_candidate(papers[0], confident=False)
        return None
