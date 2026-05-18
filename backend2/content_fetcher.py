"""
content_fetcher.py — Fetch text content from URLs (web pages and PDFs).

Call resolve_content(text) before storing a ContentSource.
If the text looks like a URL, it fetches the page and returns extracted text.
Otherwise returns the original text unchanged.
"""
import re
import httpx

_URL_RE = re.compile(r'^https?://', re.IGNORECASE)

_HEADERS = {
    "User-Agent": "ChainSight/1.0 (+supply-chain-agent)",
    "Accept": "text/html,application/pdf,*/*",
}


async def resolve_content(text: str) -> str:
    """If text is a URL, fetch and return its text content. Otherwise pass through."""
    stripped = text.strip()
    if not _URL_RE.match(stripped):
        return stripped  # plain text, return as-is

    url = stripped
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_HEADERS) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            if "pdf" in content_type or url.lower().endswith(".pdf"):
                return await _extract_pdf_text(response.content, url)

            # HTML or plain text — strip tags
            raw = response.text
            return _strip_html(raw)[:12000]  # cap at 12k chars for Gemini context

    except Exception as e:
        # Return a stub so the pipeline still runs with an error note
        return f"[URL fetch failed for {url}: {e}]\nPlease paste the content directly."


async def _extract_pdf_text(content: bytes, url: str) -> str:
    """Extract text from PDF bytes. Uses pypdf if available, else base64 stub."""
    try:
        import io
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(io.BytesIO(content))
        pages_text = []
        for page in reader.pages[:20]:  # max 20 pages
            t = page.extract_text() or ""
            if t.strip():
                pages_text.append(t.strip())
        if pages_text:
            combined = "\n\n".join(pages_text)
            return combined[:12000]
        return f"[PDF at {url} had no extractable text — please paste content directly.]"
    except ImportError:
        return (
            f"[PDF detected at {url} — pypdf not installed. "
            "Install it with: pip install pypdf, or paste the PDF text directly.]"
        )
    except Exception as e:
        return f"[PDF extraction failed for {url}: {e}]"


def _strip_html(html: str) -> str:
    """Very lightweight HTML tag stripper — no dependencies."""
    import re
    # Remove script/style blocks
    html = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()
