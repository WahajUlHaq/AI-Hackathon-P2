# Stage 1 — Tool Calls Trace
**Module**: `agents/stage1/`
**Version**: 1.0.0
**Created**: 2026-05-16T04:00:00+05:00

---

## Overview

This trace documents the external tool calls and dependencies invoked by the Stage 1 parser agents during execution. Since these agents are deterministic and do not use LLMs, "tool calls" in this context refer to library invocations, system interactions, and network requests.

---

## 1. Network Requests (Agent 1b — URL Scraper)

| Call Signature | Description | Result |
|---|---|---|
| `requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15, allow_redirects=True)` | Primary fetch of web content. | HTTP 200/404/Timeout. |
| `newspaper.Article(url).download()` | Fallback fetch of web content. | Raw HTML downloaded. |

**Observations**:
- User-Agent spoofing is used to prevent immediate 403 Forbidden errors from basic WAFs.
- `timeout=15` ensures the entire ThreadPoolExecutor doesn't hang indefinitely on a slow site.
- In demo mode, `https://example.com` returns a valid 200 OK but gets filtered out as noise due to insufficient word count.

---

## 2. File System / Data I/O

| Call Signature | Description | Result |
|---|---|---|
| `open(content, "rb").read()` | (Agent 1a) Attempts to read PDF from disk. | `bytes` or `FileNotFoundError`. |
| `base64.b64decode(content)` | (Agent 1a) Fallback if file path fails. | `bytes` or `ValueError`. |
| `io.BytesIO(pdf_bytes)` | (Agent 1a) Wraps bytes for parser ingestion. | In-memory stream. |
| `io.StringIO(content)` | (Agent 1c) Wraps CSV string for `csv.DictReader`. | Text stream. |

---

## 3. Parsing Libraries

| Library Call | Purpose | Expected Output |
|---|---|---|
| `pdfplumber.open(stream)` | (Agent 1a) Primary PDF parsing. | Page objects with text & tables. |
| `PyPDF2.PdfReader(stream)` | (Agent 1a) Fallback PDF parsing. | Page objects with basic text. |
| `BeautifulSoup(html, "lxml")` | (Agent 1b) DOM parsing & cleanup. | Navigable DOM tree. |
| `newspaper.Article(url).parse()` | (Agent 1b) Article body extraction. | Clean article text, authors, dates. |
| `csv.DictReader(stream)` | (Agent 1c) CSV parsing. | List of dictionaries (rows). |
| `json.loads(content)` | (Agent 1d, 1e) JSON parsing. | Python dict or list. |

---

## 4. Date and Time Processing

| Call Signature | Description | Result |
|---|---|---|
| `datetime.now(timezone.utc).isoformat()` | Generate fallback `received_at` timestamps. | ISO-8601 string. |
| `datetime.fromisoformat(date_str)` | Parse dates for staleness calculation. | `datetime` object. |
| `datetime.strptime(raw, fmt)` | Try multiple formats for normalized dates. | `datetime` object or `ValueError`. |

**Format Attempts**:
- `%Y-%m-%dT%H:%M:%S%z`
- `%Y-%m-%dT%H:%M:%SZ`
- `%Y-%m-%d`
- `%B %d, %Y`
- `%d %B %Y`
- `%m/%d/%Y`

---

## 5. Concurrency Management

| Call Signature | Description | Result |
|---|---|---|
| `ThreadPoolExecutor(max_workers=5)` | Orchestrate parallel execution. | Executor instance. |
| `executor.submit(parser.parse, source)` | Dispatch individual parser jobs. | Future object. |
| `as_completed(futures)` | Collect results as they finish. | Iterator over completed Futures. |

**Observations**:
- Thread pool completely abstracts thread creation and joining.
- Handles exceptions within threads cleanly via `future.result()`.
