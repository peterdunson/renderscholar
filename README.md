# 📚 renderscholar

**renderscholar** lets you search Google Scholar from the terminal, scrape papers, and render them into a static HTML page.  
The HTML includes two views:

- 👤 **Human View** — nicely formatted papers (title, authors, year, citations, link, snippet).  
- 🤖 **LLM View** — plain-text block you can copy-paste into ChatGPT/Claude/etc.  

Inspired by [Andrej Karpathy’s `rendergit`](https://github.com/karpathy/rendergit).

---

## 🔧 Installation

You’ll need **Python 3.10+**. Then install directly from GitHub:

```bash
pip install git+https://github.com/peterdunson/renderscholar.git
````

### First-time setup

Playwright requires one extra step (to install the headless Chromium browser it uses):

```bash
playwright install chromium
```

---

## 🚀 Usage

Search Google Scholar from the terminal:

```bash
renderscholar "Bayesian nonparametric survival analysis"
```

Options:

* `--pool-size N` → number of raw results to scrape (default: 100)
* `--filter-top-k N` → number of top papers to keep after ranking (default: 20)
* `--algo standard|bayesian` → ranking algorithm

  * `standard` → fast heuristic (query similarity + citations + recency)
  * `bayesian` → Bayesian linear model (slower, more nuanced)
* `--no-open` → don’t auto-open in browser
* `-o out.html` → write to a specific file instead of a temp file

Example:

```bash
renderscholar "Bayesian factor models in genomics" --pool-size 80 --filter-top-k 15 --algo bayesian
```

This will:

1. Open Scholar in a Chromium browser (so you can solve captcha if needed).
2. Scrape ~80 results.
3. Rank and filter to the top 15.
4. Render an HTML file and open it in your browser.

---

## 📂 Output

* 👤 **Human View**

  ![Human View Screenshot](docs/human_view.png)

* 🤖 **LLM View**

  ![LLM View Screenshot](docs/llm_view.png)

---

## 📝 Notes

* If you see a captcha, just solve it in the opened browser — scraping will resume automatically.
* The LLM view is plain Unicode text (titles, authors, citations, links, snippets).
* Designed for research workflows: quickly scan papers, then copy results into your favorite AI assistant.

---

## 📄 License

MIT © 2025 Peter Dunson

```

