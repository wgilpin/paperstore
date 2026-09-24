# Reading lists

## Problem

Will sometimes asks an LLM for a reading list. It stays in a chat, and he must search to find it. Progress lives only in his memory, so lists get partly read and then forgotten. PaperStore has no lists and no read state.

## Who it is for

Will, alone. A list arrives occasionally. He reads on the desktop, never on his phone.

## The smallest thing that proves it

1. **Release 1: lists of papers.** Will pastes a reading list and names it. The app splits it into ordered items and keeps the LLM's note on each. For each paper, it looks in the library, then outside. Will reviews the matches before anything is saved. A found item links to a library paper. An unfound item stays as text or a URL, or Will drops it. A supported paper URL is ingested and linked; any other URL stays a plain link. For a paper found without a free PDF, Will can upload the PDF, and the paper is ingested and linked. Will ticks items as he reads. A paper's read state is shared across lists and shows in the library.
2. **MVP test.** Will uses Release 1 on real lists. It passes if he finishes most of one list. If it fails, Release 2 does not start.
3. **Release 2: non-paper material.** Books, articles, pasted text and non-paper PDFs become typed library entries. Pasted text takes its title, authors and year from the list item's citation.

Release 1 must not block Release 2. Both use one library, and a list item links to any entry in it.

## Out of scope

- Creating a list directly from a chat. Paste is enough for occasional use.
- A checklist on the phone. The phone stays a share target for adding papers.
- Per-list read state for papers.
- List editing beyond rename, drop item and delete list (no add, reorder or archive). Rename added by ISS-15.
- No change to the current paper submission, search, tags, notes, or Drive storage.

## Open questions

- Is the real problem losing track of the list, or not finding time to read? This feature only fixes the first.
- How long does the MVP test run before it counts as failed?
- Does Zotero already cover this well enough?
