# Reading lists

## Problem
Will sometimes asks an LLM for a reading list. The list stays in a Claude chat or project, so he must search to find it again. Progress through the list lives only in his memory. The result is that lists get partly read and then forgotten. The frequency is low ("occasional use"). The cost of inaction is small per list, but the lists he asked for are not finished.

## Proposed change
Add reading lists to PaperStore. Will pastes the raw LLM output and names the list. Gemini splits it into ordered items and keeps any note the LLM wrote for each item. For each paper, the app looks in the library first and then searches external sources for it. Will reviews the matches before anything is saved. Each item on the list is either a link to a PaperStore paper or a plain text / URL item. Will ticks items as he reads them. Papers get a library-wide read / unread flag.

## Releases

### Release 1 — lists of papers
- Paste an LLM reading list and name it. Gemini parses it into ordered items with their notes.
- Match each paper against the library, then search external sources. Review the matches before import.
- A found item links to a PaperStore paper. An unfound item is plain text or a URL, or it is dropped.
- A supported URL on an unfound item (arXiv, bioRxiv, alphaXiv, direct PDF) ingests and links. Any other URL stays a plain link.
- Read / unread flag on papers, with a library filter. Non-paper items have their own tick on the list item.
- Success test: Will finishes most of one list.

### Release 2 — non-paper material in the library
- Library entries get a type (paper, book, article, video, note). The library view defaults to papers.
- An unfound list item can take a PDF upload or pasted text. Either becomes a library entry.
- Pasted text takes its title, authors and year from the list item's citation. Pasted text is only possible inside the list flow, because outside it there is no citation.
- Non-paper library entries get the same read flag, tags, notes and full-text search as papers.
- Plain URLs that are not ingested can stay list-only items.

Release 1 must not block Release 2. A list item must be able to point to any library entry, not only to a paper.

## Key decisions made during exploration
- Read state is per paper, not per list item: a paper read on one list is read on all lists. It also gives the main library a read / unread filter.
- Non-paper items (plain text, URLs) have their own tick on the list item. Their tick does not touch the library.
- Release 1: non-paper content does not enter the library. PaperStore stays a paper library. No ingestion of arbitrary content, no pasted-text entries, no book or article types.
- Release 2: non-paper content enters the library with a type field. This reverses the Release 1 rule on purpose, after Release 1 proves the core.
- List order is kept, and the LLM's per-item notes are kept: reading lists are often sequenced.
- A review step comes before import: automatic matching gets wrong papers, and LLMs invent citations.
- Unfound items: Will can drop the item, search manually, or keep it as plain text / URL.
- A URL added to an unfound item is ingested and linked if it is a supported source (arXiv, bioRxiv, alphaXiv, direct PDF). Any other URL stays a plain link that opens in the browser.
- Dedupe uses arXiv ID or DOI as the key. The app must find the ID by title search first, because LLM citations rarely include one, and included DOIs are often invented.
- Input is paste only: an endpoint or MCP tool that lets Claude create the list directly is not worth it for occasional use.
- Desktop only: Will does not read on his phone. The mobile PWA is a share target for adding papers, and it needs no checklist view.
- Success criterion: Will finishes most of one list.

## Open questions
- Is the problem losing track of the list, or not finding time to read? The feature only fixes the first. Not answered during exploration.
- Which external source does citation search use (Semantic Scholar, OpenAlex, Crossref, arXiv search)? What rate limits apply?
- How does the current dedupe work, and do existing library papers store an arXiv ID or DOI to match against?
- Can lists be edited after import (add, remove, reorder items)?
- Does a list have a finished or archived state?
- How does the review step show a weak or doubtful match compared to a confident one?

## Red-team findings
The idea survived, in a reduced form. The strongest objection: the status quo can fix about half of the problem at zero cost. Ask Claude for the list as a markdown checklist with arXiv / DOI links and keep it in the Obsidian vault. That fixes "can't find the list" and gives ticks, but it does not put papers in the library or PDFs in Drive. This objection was not fully rejected. It was answered by cutting scope: the MVP drops item types, pasted text and arbitrary ingestion, and it reuses the existing ingestion path.

A second objection: if the real problem is lack of reading time, a better checklist will not help. The cheapest experiment is to run the Obsidian checklist on the next list and see if most of it gets finished. This was not run.

Prior art to check before building: Zotero adds items from a DOI or arXiv ID and has collections. Plugins add read status. Not checked.

## Feasibility flags
- Citation search by title and authors is a new capability. Today PaperStore only ingests from a URL it is given. It needs a new external dependency with rate limits. It is the hardest part and the most likely to disappoint, because many journal papers have no free PDF.
- Title-based matching against the existing library is fuzzier than the current dedupe.

## Out of scope
- Non-paper items in the library (books, articles, videos, pasted text): moved to Release 2.
- PDF upload and text paste on list items: moved to Release 2. In Release 1, upload works through the normal library path.
- Creating lists directly from Claude through an endpoint or MCP tool: paste is enough for occasional use.
- Mobile checklist view: Will does not read on his phone.
- Per-list read state for papers: per-paper was chosen.

## Ready for /specify?
Conditional. The product shape is clear enough to specify. Two things come first: decide the citation search source, and check how dedupe works today. Running the Obsidian checklist experiment on the next list first is also recommended, but it is not blocking.
