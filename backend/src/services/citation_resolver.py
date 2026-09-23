"""Citation resolver — finds the paper a reading-list citation refers to.

Sources are tried in order and each sits behind a small function, so tests can
replace them: the library by arXiv ID, by DOI, then by title similarity.
"""

import difflib
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.schemas.reading_list import Candidate, ParsedItem
from src.services.arxiv_client import extract_arxiv_id

_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;]+)", re.IGNORECASE)
# pg_trgm similarity a library title must reach to be considered at all.
_LIBRARY_TITLE_SIMILARITY = 0.6
# Title agreement needed before the year or author check can make a match confident.
_TITLE_MATCH = 0.85


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


class CitationResolver:
    """Finds the best match for one citation."""

    def resolve(self, query: ParsedItem, db: Session) -> Candidate | None:
        """Return the best match for *query*, or None when nothing matches."""
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
