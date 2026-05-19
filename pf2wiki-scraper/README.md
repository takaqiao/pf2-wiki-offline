# pf2wiki-scraper

Scrape `https://pf2.huijiwiki.com` to build a supplemental EN/ZH glossary for PF2e translation work.

## Why the weird browser dance

The site sits behind Cloudflare. Plain `curl`, `requests`, even Playwright's `APIRequestContext` all hit 403 with a JS challenge page. The fix is to run API calls from **inside** a real browser (`page.evaluate` + `fetch`) so CF sees the genuine TLS fingerprint, UA, and cookies. A persistent user-data dir keeps the `cf_clearance` cookie across runs.

## Setup (Windows, once)

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m playwright install chromium
```

## Pipeline

Run in this order. Each step reads the previous step's output from `out/`.

| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `probe.py` | Opens a browser, clears CF, fetches siteinfo + 10 sample titles. Run first to confirm the TLS/cookie path works. | `out/probe-result.json` |
| 2 | `harvest_titles.py` | Enumerates every title across content namespaces via `list=allpages`, plus redirect sources from `list=allredirects`. | `out/titles.json`, `out/redirects.json` |
| 3 | `dump_wikitext.py [ns…]` | For each namespace, walks `generator=allpages` + `prop=revisions` and appends one JSONL record per page. Resumable — Ctrl-C is safe, rerun to continue. | `out/wikitext/<nsid>.jsonl`, `out/wikitext/_state.json` |
| 4 | `extract_terms.py` | Regexes EN/ZH pairs out of every wikitext dump using 6 patterns (see below). | `out/glossary_wiki.json` (all), `out/glossary_wiki_confident.json` (multi-source/count), `out/glossary_wiki_short_zh.json` (ZH ≤ 8 chars), `out/glossary_wiki.csv`, `out/extract_report.md` |
| 5 | `diff_against_glossary.py [user.json] [full\|confident\|short]` | Diffs the wiki extract against the user's existing glossary. New terms + translation conflicts. Defaults to `confident`. | `out/new_terms_<src>.json`, `out/conflicts_<src>.json`, `out/diff_report_<src>.md` |
| 6 | `build_supplement.py [user.json]` | Builds a merge-ready flat `{en: zh}` supplement file. Uses the **confident ∩ short_zh** intersection, drops entries already in user glossary, filters sentence fragments. | `out/glossary_supplement.json`, `out/glossary_supplement_preview.md` |

## Term-extraction patterns

1. **A_title_field** — `|title=ZH EN` or `|title=EN ZH` inside Statblock templates.
2. **B_triple_bold** — `'''ZH EN'''` bolded in prose.
3. **C_html_bold** — `<b>ZH EN</b>` HTML bold.
4. **D_paren_ZHopenEN** / **D_paren_ENopenZH** — `ZH（EN）`, `ZH (EN)` and the inverse.
5. **E_infobox_field** — `|英文名=`, `|english_name=`, `|eng=` etc. paired with `|中文名=` / page title.
6. **F_lang_template** — `{{lang|en|Foo}}` with nearest ZH preceding.

## Current numbers (initial full run)

- Pages scanned: **36,971**
- Unique EN terms found: **16,382**
- Confident subset (≥2 sources or ≥2 hits): **4,614**
- Merge-ready supplement (not in user glossary): **~3,838** new entries

## Re-running

- **Titles only**: re-run `harvest_titles.py` — overwrites `out/titles.json`.
- **Incremental dump**: `dump_wikitext.py` keeps `_state.json`; rerun to resume.
- **Fresh dump**: delete `out/wikitext/` and rerun.
- **Extraction / diff / supplement**: always safe to rerun in seconds.

## Files to review manually

- `out/glossary_supplement.json` — paste-ready for merging.
- `out/conflicts_confident.json` — where wiki disagrees with your glossary. Hand-pick the ones you want.
- `out/diff_report_confident.md` — glanceable markdown summary.
