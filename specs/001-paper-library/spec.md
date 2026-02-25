# Feature Specification: Academic Paper Library

**Feature Branch**: `001-paper-library`
**Created**: 2026-02-25
**Status**: Draft
**Input**: User description: "an app that allows the collection, viewing, searching of academic papers. The user can open the app and paste a url to a pdf or to an arxiv paper, and the paper will be processed and uploaded. Metadata to be extracted includes author list, title, date of publication, abstract. There is also a chrome extension that will do the same, either from a web page for the paper with a pdf link (start with arxiv pages only), or from a pdf in chrome. Files will be stored in Drive. The metadata will be stored in postgresql. In the app, the user can add notes if they want - a single note block. The user can open the app and perform a text search on any of the metadata fields, find a list of papers, and view in-app if they choose"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add Paper via URL (Priority: P1)

A researcher opens the web app and pastes either an arXiv page URL or a direct PDF URL into an input field. The system fetches the paper, extracts its metadata (title, authors, publication date, abstract), stores the PDF file, and saves the metadata. The paper then appears in the user's library.

**Why this priority**: This is the core intake mechanism — without it, no papers can be collected and the entire library has no content. All other stories depend on papers being present.

**Independent Test**: Paste an arXiv URL and a direct PDF URL into the app; confirm both are processed and appear in the library with correct metadata and a viewable PDF.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** the user pastes a valid arXiv page URL and submits, **Then** the app shows a loading indicator while processing; once complete, the paper appears in the library with extracted title, authors, publication date, and abstract.
2. **Given** the app is open, **When** the user pastes a direct PDF URL and submits, **Then** the app shows a loading indicator while downloading and processing; once complete, the paper appears in the library with available metadata.
3. **Given** the user submits a URL, **When** the URL is unreachable or not a recognised PDF or arXiv page, **Then** the system shows a clear error message and no partial record is created.
4. **Given** the user submits a URL for a paper already in the library, **When** the system detects a duplicate (by URL or arXiv ID), **Then** the user is informed and no duplicate record is created.

---

### User Story 2 - Search and Browse Library (Priority: P2)

A researcher opens the web app and types a search query into a search box. The system searches across all metadata fields (title, authors, abstract, publication date) and returns a list of matching papers. The user can scroll through results and select a paper to view its details.

**Why this priority**: Without search, the library is only useful if it contains very few papers. Search is what makes the collection valuable at scale.

**Independent Test**: With several papers in the library, enter a term that matches some but not all papers; confirm only matching papers are returned and the results are accurate.

**Acceptance Scenarios**:

1. **Given** the library contains papers, **When** the user enters a search term matching paper titles, **Then** only papers with that term in their metadata are shown.
2. **Given** the library contains papers, **When** the user enters an author's name, **Then** all papers by that author are returned.
3. **Given** the library contains papers, **When** the user clears the search box, **Then** all papers are shown in newest-first order (by date added).
4. **Given** the library is empty or no results match, **When** the user searches, **Then** a clear "no results" message is displayed.

---

### User Story 3 - View Paper In-App (Priority: P3)

From the search results or library list, a researcher selects a paper and views its details — including full metadata and the PDF — without leaving the app.

**Why this priority**: Viewing papers in-app closes the loop; without it users must navigate elsewhere to read papers they've collected.

**Independent Test**: Select a paper from the library list and confirm the metadata panel and PDF viewer both display correctly within the app.

**Acceptance Scenarios**:

1. **Given** a paper exists in the library, **When** the user selects it from the list, **Then** the full metadata (title, authors, date, abstract) is displayed alongside an in-app PDF viewer.
2. **Given** the user is viewing a paper, **When** they navigate back, **Then** they return to their previous search results or library list.

---

### User Story 4 - Add and Edit Notes on a Paper (Priority: P4)

A researcher selects a paper and writes a personal note in a single free-text note block attached to that paper. The note is saved and persists across sessions.

**Why this priority**: Notes add personal context to collected papers; useful but not essential for the core collection and search MVP.

**Independent Test**: Open a paper, type a note, close the app, reopen it, and confirm the note is still present on that paper.

**Acceptance Scenarios**:

1. **Given** a paper is open, **When** the user types in the note field and clicks away (blur), **Then** the note is saved automatically and visible the next time the paper is opened.
2. **Given** a paper has an existing note, **When** the user edits the note field and clicks away, **Then** the updated note replaces the previous content.
3. **Given** a paper has no note, **When** the user opens it, **Then** an empty note field is shown ready for input.

---

### User Story 5 - Add Paper via Chrome Extension (Priority: P5)

While browsing an arXiv paper page in Chrome, a researcher clicks the PaperStore extension icon. The extension detects the arXiv paper, sends it to PaperStore for processing, and the paper appears in the user's library — without the user needing to copy any URL.

**Why this priority**: The Chrome extension reduces friction for the most common workflow (browsing arXiv), but it duplicates the URL-paste flow and can be deferred until the core app is stable.

**Independent Test**: Navigate to an arXiv paper page in Chrome, activate the extension, and confirm the paper appears in the library with correct metadata.

**Acceptance Scenarios**:

1. **Given** the user is on an arXiv paper page in Chrome, **When** they click the extension icon, **Then** the extension sends the paper to PaperStore and the paper appears in the library.
2. **Given** the user is on a non-arXiv page or a page with no detectable paper, **When** they click the extension icon, **Then** the extension shows a message explaining it cannot process the current page.
3. **Given** the paper is already in the library, **When** the user activates the extension on its arXiv page, **Then** the user is informed of the duplicate and no second record is created.

---

### Edge Cases

- What happens when a PDF URL redirects multiple times before resolving?
- How does the system handle a PDF that cannot yield metadata (e.g., a scanned image-only PDF with no text layer)?
- What happens if the file storage service is unavailable when the user submits a paper?
- What if two papers share the same title but are different works?
- What happens when an arXiv page has missing metadata fields (e.g., no listed authors)?
- What if the user submits the same arXiv paper via different URL forms (e.g., `abs/`, `pdf/`, versioned URL)?

## Requirements *(mandatory)*

### Functional Requirements

#### Authentication

- **FR-000**: Users MUST authenticate via Google OAuth before accessing any part of the app. Unauthenticated requests and expired sessions MUST be redirected to the Google sign-in flow. After successful re-authentication, the user MUST be returned to the page they were on. The authenticated Google account MUST be the same account used for Google Drive access.

#### Paper Ingestion

- **FR-001**: Users MUST be able to submit a URL (arXiv page or direct PDF link) via the web app to add a paper to the library. Submission is synchronous — the app MUST display a loading indicator during processing and show the result (success or error) when complete.
- **FR-002**: The system MUST extract the following metadata from submitted papers: title, author list, publication date, and abstract.
- **FR-003**: The system MUST store the PDF file in Google Drive upon successful ingestion.
- **FR-004**: The system MUST persistently store paper metadata including title, authors, publication date, abstract, file storage reference, submission URL, and arXiv ID (where applicable).
- **FR-005**: The system MUST detect duplicate submissions (matching URL or arXiv ID) and reject them with a user-visible message.
- **FR-006**: The system MUST show a clear error message when a URL cannot be processed (unreachable, unsupported format, or metadata parse failure).

#### Search & Browse

- **FR-007**: Users MUST be able to search the library using a free-text query matched against title, author list, abstract, and publication date.
- **FR-008**: The system MUST return a list of matching papers in response to a search query.
- **FR-009**: Users MUST be able to browse all papers in the library when no search query is active. The default order MUST be newest-first (by date added to the library).

#### Viewing

- **FR-010**: Users MUST be able to select a paper from the library list and view its full metadata within the app.
- **FR-011**: Users MUST be able to view the paper's PDF within the app without downloading it separately.

#### Notes

- **FR-012**: Each paper MUST support exactly one associated plain-text note field.
- **FR-013**: Users MUST be able to create and edit a note on any paper. The note MUST be saved automatically when the user moves focus away from the note field (on blur). No explicit save button is required.
- **FR-014**: Notes MUST persist between sessions.

#### Chrome Extension

- **FR-015**: A Chrome extension MUST allow users to submit the current arXiv page to the library with a single click.
- **FR-016**: The extension MUST communicate submission status (success, duplicate, or error) to the user.
- **FR-017**: The extension MUST show a clear message when activated on a page it cannot process.

### Key Entities

- **Paper**: The primary record representing a collected academic paper. Attributes: unique identifier, title, author list, publication date, abstract, Google Drive file reference, submission URL, arXiv ID (if applicable), date added to library.
- **Note**: A single plain-text annotation block associated with one Paper. Attributes: reference to parent Paper, text content, last modified timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can submit an arXiv URL and have the paper appear in their library within 30 seconds under normal network conditions.
- **SC-002**: A user can submit a direct PDF URL and have the paper appear in their library within 60 seconds under normal network conditions.
- **SC-003**: A search query across a library of 500 papers returns results in under 2 seconds.
- **SC-004**: All well-formed arXiv submissions produce correctly extracted title, authors, date, and abstract.
- **SC-005**: A note added to a paper is retrievable on every subsequent visit to that paper (zero data loss).
- **SC-006**: The Chrome extension adds an arXiv paper to the library in a single click with no URL copying required.
- **SC-007**: Duplicate submissions (identical URL or arXiv ID) are rejected 100% of the time.

## Clarifications

### Session 2026-02-25

- Q: What authentication mechanism should protect the app? → A: Google OAuth — the same Google account used for Drive access is used to authenticate the user into the app.
- Q: How does the note field save? → A: Auto-save on blur — note is saved when the user clicks away from the text field.
- Q: Is paper submission synchronous or asynchronous? → A: Synchronous — the app shows a loading/spinner state while processing; the paper appears in the library when complete.
- Q: What happens when the Google OAuth session expires at runtime? → A: Redirect to re-authentication — the app detects the expired session and redirects the user to the Google sign-in flow, then returns them to the app.
- Q: What is the default sort order for the library list? → A: Newest first — papers ordered by date added to the library, most recent at top.

## Assumptions

- Google Drive is the intended file storage service; the same Google OAuth flow used for Drive access also authenticates the user into the app.
- The app is a single-user tool; only the authenticated Google account owner can access the library. Multi-user access, sharing, and permissions are out of scope.
- The Chrome extension scope is arXiv pages only; other academic sites are explicitly out of scope for this version.
- Metadata extraction for non-arXiv PDFs uses best-effort parsing of PDF document properties; missing fields are acceptable and displayed as blank.
- In-app PDF viewing uses the browser's built-in PDF rendering capability; no custom renderer is required.
- Notes are plain text only; rich text formatting is out of scope.
- Search is keyword/substring match across stored metadata fields; semantic or AI-powered search is out of scope.
- "View in-app" for PDFs means the PDF is served from the application (via the Drive file) and rendered in an embedded viewer on the same page.
