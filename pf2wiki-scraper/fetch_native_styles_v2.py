"""Fetch all CSS used by pf2.huijiwiki.com (skin-huiji-dragonhide + gadgets + smw)
and bundle into _wiki_full_v2/assets/wiki_native.css. Localizes url(...) refs.

Run AFTER cookies are fresh:
    .venv\\Scripts\\python.exe fetch_native_styles_v2.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

from bs4 import BeautifulSoup
from curl_cffi import requests as crequests

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "_wiki_full_v2"
ASSETS = OUT / "assets"
NATIVE_DIR = ASSETS / "native"
NATIVE_DIR.mkdir(parents=True, exist_ok=True)
COOKIES_FILE = ROOT / "out_v2" / "cookies.json"

BASE = "https://pf2.huijiwiki.com"
SAMPLE_PAGE = f"{BASE}/wiki/%E6%88%98%E5%A3%AB"  # 战士
IMPERSONATE = "chrome131"


def make_session(cookies: list[dict]) -> "crequests.Session":
    s = crequests.Session(impersonate=IMPERSONATE)
    s.headers.update({
        "Accept": "text/html,application/xhtml+xml,text/css,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": SAMPLE_PAGE,
    })
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ".huijiwiki.com"), path=c.get("path", "/"))
        except Exception:
            s.cookies[c["name"]] = c["value"]
    return s


URL_REF_RX = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def localize_css(css_text: str, base_url: str, session: "crequests.Session") -> tuple[str, dict[str, str]]:
    """Find all url() refs in CSS, download them to native/, rewrite to local paths.

    Returns (rewritten_css, url_to_local_filename_map).
    """
    asset_map: dict[str, str] = {}
    seen: dict[str, str] = {}
    refs = set()
    for m in URL_REF_RX.finditer(css_text):
        ref = m.group(2)
        if ref.startswith(("data:", "#", "//mw")):
            continue
        refs.add(ref)

    print(f"    found {len(refs)} url() refs")
    for ref in sorted(refs):
        full = urljoin(base_url, ref)
        if full in seen:
            continue
        # Determine filename
        url_path = unquote(urlparse(full).path)
        if "." in url_path.split("/")[-1]:
            ext = url_path.rsplit(".", 1)[-1].lower().split("?")[0]
        else:
            ext = "bin"
        if ext in {"woff2", "woff", "ttf", "eot", "otf"}:
            kind = "font"
        elif ext in {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico"}:
            kind = "img"
        else:
            kind = "asset"
        h = hashlib.sha1(full.encode()).hexdigest()[:16]
        fname = f"{kind}_{h}.{ext}"[:80]
        try:
            r = session.get(full, timeout=30)
            if r.status_code == 200:
                (NATIVE_DIR / fname).write_bytes(r.content)
                seen[full] = fname
                asset_map[ref] = fname
            else:
                print(f"      [{r.status_code}] {full[:100]}")
        except Exception as e:
            print(f"      [err] {full[:100]}: {type(e).__name__}")

    def rewrite(m: re.Match) -> str:
        quote, ref = m.group(1), m.group(2)
        if ref.startswith(("data:", "#", "//mw")):
            return m.group(0)
        local = asset_map.get(ref)
        if not local:
            full = urljoin(base_url, ref)
            local = seen.get(full)
        if local:
            return f"url({quote}native/{local}{quote})"
        return m.group(0)

    rewritten = URL_REF_RX.sub(rewrite, css_text)
    print(f"    downloaded {len(seen)} assets, rewrote refs")
    return rewritten, asset_map


def main() -> int:
    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} missing — run cookie_warmup_v2.py first")
        return 1
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    session = make_session(cookies)

    print(f"[1/4] fetching sample page {SAMPLE_PAGE}")
    r = session.get(SAMPLE_PAGE, timeout=30)
    if r.status_code != 200:
        print(f"ERROR: status {r.status_code}")
        return 1
    soup = BeautifulSoup(r.text, "lxml")

    # Stylesheet hrefs (preserve order)
    css_urls: list[str] = []
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            css_urls.append(urljoin(BASE, href))
    print(f"[2/4] found {len(css_urls)} stylesheet URLs")
    for u in css_urls:
        print(f"    {u[:140]}")

    # Inline <style> blocks
    inline_styles: list[str] = []
    for style in soup.find_all("style"):
        if style.string:
            inline_styles.append(style.string)
    print(f"    + {len(inline_styles)} inline <style> blocks")

    # Body class + DOM hint
    body_classes = soup.body.get("class", []) if soup.body else []
    print(f"    body classes: {body_classes}")

    # Save full HTML for reference
    (NATIVE_DIR.parent / "_native_sample_page.html").write_text(r.text, encoding="utf-8")

    print("[3/4] fetching + localizing CSS ...")
    sections: list[str] = []
    t0 = time.time()
    for url in css_urls:
        try:
            rr = session.get(url, timeout=30)
        except Exception as e:
            print(f"    [err] {url}: {e}")
            continue
        if rr.status_code != 200:
            print(f"    [{rr.status_code}] {url}")
            continue
        print(f"    [{rr.status_code}] {len(rr.text):>7} chars  {url[:120]}")
        # base_url for url() resolution is the CSS URL itself
        localized, _ = localize_css(rr.text, url, session)
        sections.append(f"/* ============================================================\n   {url}\n   ============================================================ */\n")
        sections.append(localized)
        sections.append("\n\n")

    # Append inline styles
    for i, style_text in enumerate(inline_styles):
        sections.append(f"/* ===== inline <style> #{i} ===== */\n")
        sections.append(style_text)
        sections.append("\n\n")

    combined = "".join(sections)
    out_path = ASSETS / "wiki_native.css"
    out_path.write_text(combined, encoding="utf-8")
    print(f"[4/4] wrote {out_path.name}: {len(combined)} chars ({len(combined)/1024:.1f} KB) in {time.time()-t0:.1f}s")

    # Body class hint file
    (NATIVE_DIR.parent / "_native_body_classes.txt").write_text(
        " ".join(body_classes) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
