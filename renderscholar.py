#!/usr/bin/env python3
"""
Search Google Scholar and render results into a static HTML page
with Human and LLM views.
"""

import argparse
import html
import pathlib
import sys
import tempfile
import webbrowser
from typing import List

from pygments.formatters import HtmlFormatter

from renderscholar.scholar import (
    search_scholar,
    rank_papers,
    smart_rank_papers,
    bayesian_rank_papers,
)
from renderscholar.models import format_results_for_llm


def build_html(query: str, papers: List[dict]) -> str:
    formatter = HtmlFormatter(nowrap=False)
    pygments_css = formatter.get_style_defs('.highlight')

    # 👤 Human View
    human_sections: List[str] = []
    for i, p in enumerate(papers, 1):
        title = html.escape(p.get("title", "No title"))
        authors_year = html.escape(p.get("authors_year", ""))
        snippet = html.escape(p.get("snippet", ""))
        link = p.get("pdf_link") or p.get("scholar_link") or p.get("link") or "#"
        citations = p.get("citations") or 0
        year = p.get("year") or "?"

        human_sections.append(f"""
        <section class="paper">
          <h2>{i}. {title}</h2>
          <p><strong>Authors/Year:</strong> {authors_year} ({year})</p>
          <p><strong>Citations:</strong> {citations}</p>
          <p>{snippet}</p>
          <p><a href="{link}" target="_blank">🔗 Link</a></p>
        </section>
        """)

    human_html = "\n".join(human_sections)

    # 🤖 LLM View
    llm_text = format_results_for_llm(papers)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Scholar results – {html.escape(query)}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial;
    margin: 0; padding: 0; line-height: 1.45;
  }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 1rem; }}
  h1 {{ margin-bottom: 1rem; }}
  .paper {{ border-bottom: 1px solid #eee; padding: 1rem 0; }}
  .paper h2 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; }}
  .paper p {{ margin: 0.25rem 0; }}
  .view-toggle {{
    margin: 1rem 0;
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }}
  .toggle-btn {{
    padding: 0.5rem 1rem;
    border: 1px solid #d1d9e0;
    background: white;
    cursor: pointer;
    border-radius: 6px;
    font-size: 0.9rem;
  }}
  .toggle-btn.active {{
    background: #0366d6;
    color: white;
    border-color: #0366d6;
  }}
  .toggle-btn:hover:not(.active) {{
    background: #f6f8fa;
  }}
  #llm-view {{ display: none; }}
  #llm-text {{
    width: 100%;
    height: 70vh;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.85em;
    border: 1px solid #d1d9e0;
    border-radius: 6px;
    padding: 1rem;
    resize: vertical;
  }}
  .copy-hint {{
    margin-top: 0.5rem;
    color: #666;
    font-size: 0.9em;
  }}
  {pygments_css}
</style>
</head>
<body>
<a id="top"></a>
<div class="container">

  <h1>Google Scholar results for: {html.escape(query)}</h1>
  <p>Total filtered papers: {len(papers)}</p>

  <div class="view-toggle">
    <strong>View:</strong>
    <button class="toggle-btn active" onclick="showHumanView()">👤 Human</button>
    <button class="toggle-btn" onclick="showLLMView()">🤖 LLM</button>
  </div>

  <div id="human-view">
    {human_html}
  </div>

  <div id="llm-view">
    <section>
      <h2>🤖 LLM View – Copiable Results</h2>
      <p>Copy the text below and paste it into ChatGPT/Claude/etc:</p>
      <textarea id="llm-text" readonly>{html.escape(llm_text)}</textarea>
      <div class="copy-hint">
        💡 Tip: Click in the text area and press Ctrl+A (Cmd+A) then Ctrl+C (Cmd+C) to copy.
      </div>
    </section>
  </div>

</div>

<script>
function showHumanView() {{
  document.getElementById('human-view').style.display = 'block';
  document.getElementById('llm-view').style.display = 'none';
  document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
}}

function showLLMView() {{
  document.getElementById('human-view').style.display = 'none';
  document.getElementById('llm-view').style.display = 'block';
  document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  setTimeout(() => {{
    const textArea = document.getElementById('llm-text');
    textArea.focus();
    textArea.select();
  }}, 100);
}}
</script>
</body>
</html>
"""


def derive_temp_output_path(query: str) -> pathlib.Path:
    """Temporary output path derived from query."""
    safe_query = "".join(c if c.isalnum() else "_" for c in query)
    filename = f"renderscholar_{safe_query[:30]}.html"
    return pathlib.Path(tempfile.gettempdir()) / filename


def main() -> int:
    ap = argparse.ArgumentParser(description="Search Google Scholar and render results into HTML")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--pool-size", type=int, default=50, help="Number of papers to scrape from Scholar")
    ap.add_argument("--filter-top-k", type=int, default=20, help="Number of top papers to keep after ranking")
    ap.add_argument("--algo", choices=["standard", "smart", "bayesian"], default="standard", help="Ranking algorithm")
    ap.add_argument("-o", "--out", help="Output HTML file path (default: temp file)")
    ap.add_argument("--no-open", action="store_true", help="Don't open HTML in browser after generation")
    args = ap.parse_args()

    if args.out is None:
        args.out = str(derive_temp_output_path(args.query))

    print(f"🔎 Searching Scholar for: {args.query}", file=sys.stderr)
    pool = search_scholar(args.query, pool_size=args.pool_size, sort_by="relevance", wait_for_user=True)
    print(f"✓ Retrieved {len(pool)} raw papers", file=sys.stderr)

    if args.algo == "smart":
        ranked = smart_rank_papers(args.query, pool, max_results=args.filter_top_k)
    elif args.algo == "bayesian":
        ranked = bayesian_rank_papers(args.query, pool, max_results=args.filter_top_k)
    else:
        ranked = rank_papers(args.query, pool, max_results=args.filter_top_k)

    print(f"✓ Filtered down to {len(ranked)} papers", file=sys.stderr)

    print("🔨 Generating HTML...", file=sys.stderr)
    html_out = build_html(args.query, ranked)

    out_path = pathlib.Path(args.out)
    out_path.write_text(html_out, encoding="utf-8")
    file_size = out_path.stat().st_size
    print(f"💾 Wrote {file_size/1024:.1f} KiB to {out_path}", file=sys.stderr)

    if not args.no_open:
        print(f"🌐 Opening in browser...", file=sys.stderr)
        webbrowser.open(f"file://{out_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
