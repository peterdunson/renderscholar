from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import html
from urllib.parse import quote_plus
import time
import math
import re
from difflib import SequenceMatcher
import numpy as np
import os
from datetime import datetime
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"


# NEW: semantic search
from sentence_transformers import SentenceTransformer, util

_semantic_model = None  # cache globally


def search_scholar(query: str, pool_size: int = 100, sort_by: str = "relevance", wait_for_user=False):
    """
    Scrape Google Scholar for a pool of papers.
    If captcha appears, user solves it manually in the visible browser.
    When scraping completes, prints "DONE SCRAPING" and writes scrape_done.txt.
    If wait_for_user=True, pauses until user clears captcha.
    """
    results = []
    encoded_query = quote_plus(query)
    per_page = 10
    pages = (pool_size + per_page - 1) // per_page
    sort_param = "0" if sort_by == "relevance" else "1"

    # remove any old flags
    if os.path.exists("scrape_done.txt"):
        os.remove("scrape_done.txt")
    if os.path.exists("captcha_flag.txt"):
        os.remove("captcha_flag.txt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        for i in range(pages):
            start = i * per_page
            url = f"https://scholar.google.com/scholar?hl=en&q={encoded_query}&start={start}&scisbd={sort_param}"
            print(f"DEBUG: Visiting {url}")

            page.goto(url)

            try:
                page.wait_for_selector(".gs_ri, .gs_r, .gs_or", timeout=15000)
            except Exception:
                print("⚠️ Captcha detected, please solve it in the browser.")

                if wait_for_user:
                    with open("captcha_flag.txt", "w") as f:
                        f.write("waiting")
                    while os.path.exists("captcha_flag.txt"):
                        time.sleep(1)

                page.wait_for_selector(".gs_ri, .gs_r, .gs_or", timeout=0)

            # parse entries
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            entries = soup.select(".gs_ri, .gs_r, .gs_or")
            print(f"DEBUG: Page {i}, found {len(entries)} entries")

            for entry in entries:
                title_tag = entry.select_one("h3 a")
                title = html.unescape(title_tag.text.strip()) if title_tag else "No title"
                link = title_tag["href"] if title_tag else None
                snippet = entry.select_one(".gs_rs")
                snippet_text = html.unescape(snippet.text.strip()) if snippet else ""
                authors_year = entry.select_one(".gs_a")
                authors_year_text = html.unescape(authors_year.text.strip()) if authors_year else ""
                scholar_link = None
                if title_tag and title_tag.has_attr("href"):
                    scholar_link = (
                        "https://scholar.google.com" + title_tag["href"]
                        if title_tag["href"].startswith("/scholar")
                        else title_tag["href"]
                    )
                pdf_tag = entry.select_one(".gs_or_ggsm a, .gs_ggsd a")
                pdf_link = pdf_tag["href"] if pdf_tag else None
                citations = None
                footer = entry.select_one(".gs_fl")
                if footer:
                    cite_link = footer.find("a", string=lambda s: s and "Cited by" in s)
                    if cite_link:
                        try:
                            citations = int(cite_link.text.replace("Cited by", "").strip())
                        except ValueError:
                            citations = None
                year = None
                match = re.search(r"\b(19|20)\d{2}\b", authors_year_text)
                if match:
                    year = int(match.group(0))

                results.append({
                    "title": title,
                    "link": link,
                    "scholar_link": scholar_link,
                    "pdf_link": pdf_link,
                    "snippet": snippet_text,
                    "authors_year": authors_year_text,
                    "citations": citations,
                    "year": year
                })

            time.sleep(1)

        browser.close()

    # 🔹 Signal scraping is done
    with open("scrape_done.txt", "w") as f:
        f.write("done")
    print("✅ DONE SCRAPING")

    return results


# --------------------
# Modes configuration
# --------------------
MODES = {
    "balanced": dict(w_sim=0.5, w_cites=0.3, w_recency=0.2),
    "recent": dict(w_sim=0.3, w_cites=0.2, w_recency=0.5),
    "famous": dict(w_sim=0.2, w_cites=0.7, w_recency=0.1),
    "influential": dict(w_sim=0.4, w_cites=0.4, w_recency=0.2),
    "hot": dict(w_sim=0.3, w_cites=0.4, w_recency=0.3),
    "semantic": None,  # special handling
    "single": dict(w_sim=1.0, w_cites=0.0, w_recency=0.0),  # NEW
}


def rank_papers(query: str, papers: list, max_results: int = 20, mode: str = "balanced"):
    """
    Rank papers according to the selected mode.
    Modes control weighting of similarity, citations, and recency.
    """
    if mode == "semantic":
        return semantic_rank_papers(query, papers, max_results=max_results)

    weights = MODES.get(mode, MODES["balanced"])
    w_sim, w_cites, w_recency = weights["w_sim"], weights["w_cites"], weights["w_recency"]

    scored = []
    for paper in papers:
        # similarity (title > snippet)
        sim = 0.0
        if paper.get("title"):
            sim = SequenceMatcher(None, query.lower(), paper["title"].lower()).ratio()
        elif paper.get("snippet"):
            sim = SequenceMatcher(None, query.lower(), paper["snippet"].lower()).ratio()

        # citations (log scaled)
        cites = math.log1p(paper["citations"]) if paper.get("citations") else 0.0

        # recency boost (2000 → 0.0, 2025 → 1.0)
        recency = 0.0
        if paper.get("year"):
            recency = max(0, (paper["year"] - 2000) / 25.0)

        # weighted score
        score = (w_sim * sim) + (w_cites * (cites / 10)) + (w_recency * recency)
        scored.append((score, paper))

    scored.sort(key=lambda x: x[0], reverse=True)
    # special case for "single" → only return the top paper
    if mode == "single":
        return [scored[0][1]] if scored else []

    return [p for _, p in scored[:max_results]]


def semantic_rank_papers(query: str, papers: list, max_results: int = 20):
    """
    Rank papers using semantic embeddings + citations + recency.
    """
    global _semantic_model
    if _semantic_model is None:
        print("⏳ Loading semantic model (all-MiniLM-L6-v2)...")
        _semantic_model = SentenceTransformer("all-MiniLM-L6-v2")

    query_emb = _semantic_model.encode(query, convert_to_tensor=True)

    scored = []
    for paper in papers:
        text = paper.get("title", "") + " " + (paper.get("snippet") or "")
        if not text.strip():
            continue

        doc_emb = _semantic_model.encode(text, convert_to_tensor=True)
        sim = float(util.cos_sim(query_emb, doc_emb).item())

        # citations (log scaled)
        cites = math.log1p(paper.get("citations") or 0)

        # recency boost
        recency = 0.0
        if paper.get("year"):
            recency = max(0, (paper["year"] - 2000) / 25.0)

        # weighted score (semantic similarity gets higher weight)
        score = (0.6 * sim) + (0.25 * (cites / 10)) + (0.15 * recency)
        scored.append((score, paper))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_results]]


if __name__ == "__main__":
    print("🔎 Testing scholar scraper...\n")
    pool = search_scholar("bayesian regression", pool_size=10, sort_by="relevance")
    ranked = rank_papers("bayesian regression", pool, max_results=5, mode="semantic")

    for idx, r in enumerate(ranked, 1):
        print(f"\n=== Ranked Result {idx} ===")
        for key, value in r.items():
            print(f"{key}: {value}")
