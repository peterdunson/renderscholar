from pydantic import BaseModel
from typing import Optional, List
import re

class Paper(BaseModel):
    title: str
    link: Optional[str]
    scholar_link: Optional[str]
    pdf_link: Optional[str]
    snippet: Optional[str]
    authors_year: Optional[str]
    citations: Optional[int]
    year: Optional[int]

def clean_text(text: str) -> str:
    """Remove non-ASCII characters and tidy up spaces."""
    if not text:
        return ""
    return re.sub(r"[^\x00-\x7F]+", " ", text).strip()

def format_results_for_llm(results: List[dict]) -> str:
    """
    Convert raw scraper JSON into a clean, LLM-friendly string.
    """
    output = []
    for r in results:
        title = clean_text(r.get("title", "No title"))
        authors_year = clean_text(r.get("authors_year", ""))
        snippet = clean_text(r.get("snippet", ""))
        link = r.get("pdf_link") or r.get("scholar_link") or r.get("link") or "No link"
        citations = r.get("citations", 0)
        year = r.get("year", "?")

        formatted = (
            f"📄 {title}\n"
            f"👥 {authors_year} ({year})\n"
            f"🔗 {link}\n"
            f"📑 Citations: {citations}\n"
            f"✏️ {snippet}"
        )
        output.append(formatted)

    return "\n\n".join(output)

