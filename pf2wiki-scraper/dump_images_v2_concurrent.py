"""Phase C (concurrent edition) — uses curl_cffi + CF cookies from warmup.

Scans parsed/* for image titles, batches imageinfo API, downloads originals.
~10-20x faster than Playwright-based dump_images_v2.py.

Pre-req:
    .venv\\Scripts\\python.exe cookie_warmup_v2.py

Run:
    .venv\\Scripts\\python.exe dump_images_v2_concurrent.py             # 16 workers
    .venv\\Scripts\\python.exe dump_images_v2_concurrent.py -c 24
    .venv\\Scripts\\python.exe dump_images_v2_concurrent.py --limit 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse, unquote

from curl_cffi import requests as crequests

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
PARSED_DIR = OUT_V2 / "parsed"
IMAGES_DIR = OUT_V2 / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_FILE = IMAGES_DIR / "manifest.json"
COOKIES_FILE = OUT_V2 / "cookies.json"

API_URL = "https://pf2.huijiwiki.com/api.php"
HOMEPAGE_URL = "https://pf2.huijiwiki.com/wiki/%E9%A6%96%E9%A1%B5"
IMPERSONATE = "chrome131"
IMAGEINFO_BATCH = 50

manifest_lock = threading.Lock()


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def save_manifest(m: dict) -> None:
    with manifest_lock:
        MANIFEST_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_image_titles() -> list[str]:
    seen: set[str] = set()
    n_files = 0
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.name.endswith(".json"):
                continue
            n_files += 1
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            for img in (doc.get("parse") or {}).get("images", []) or []:
                seen.add(img)
    print(f"  [collect] scanned {n_files} parsed files, {len(seen)} unique image titles")
    return sorted(seen)


def make_session(cookies: list[dict]) -> "crequests.Session":
    s = crequests.Session(impersonate=IMPERSONATE)
    s.headers.update({
        "Accept": "application/json, image/*, */*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": HOMEPAGE_URL,
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
    })
    for c in cookies:
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ".huijiwiki.com"), path=c.get("path", "/"))
        except Exception:
            s.cookies[c["name"]] = c["value"]
    return s


def sha_to_local(sha1: str, ext: str) -> Path:
    return IMAGES_DIR / sha1[:2] / f"{sha1[2:]}.{ext}"


def ext_from_url_or_mime(url: str, mime: str) -> str:
    path = unquote(urlparse(url).path)
    if "." in path:
        e = path.rsplit(".", 1)[-1].lower()
        if e in {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "tiff", "ico", "pdf"}:
            return e
    m = (mime or "").lower()
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/gif": "gif",
        "image/svg+xml": "svg",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
        "image/x-icon": "ico",
        "application/pdf": "pdf",
    }.get(m, "bin")


def fetch_imageinfo_batch(session: "crequests.Session", titles: list[str]) -> dict:
    titles_param = "|".join(f"File:{t}" if not t.startswith("File:") else t for t in titles)
    params = {
        "action": "query",
        "titles": titles_param,
        "prop": "imageinfo",
        "iiprop": "url|size|sha1|mime|timestamp",
        "format": "json",
        "formatversion": "2",
    }
    r = session.get(API_URL, params=params, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"imageinfo http {r.status_code}: {r.text[:200]}")
    j = r.json()
    out: dict[str, dict] = {}
    for p in (j.get("query") or {}).get("pages", []) or []:
        title = p.get("title", "")
        bare = title[5:] if title.startswith("File:") else title
        if p.get("missing"):
            out[bare] = {"missing": True}
            continue
        ii_list = p.get("imageinfo") or []
        if not ii_list:
            out[bare] = {"missing": True}
            continue
        ii = ii_list[0]
        out[bare] = {
            "url": ii.get("url"),
            "width": ii.get("width"),
            "height": ii.get("height"),
            "size": ii.get("size"),
            "sha1": ii.get("sha1"),
            "mime": ii.get("mime"),
            "timestamp": ii.get("timestamp"),
        }
    return out


def download_one(session: "crequests.Session", url: str, dest: Path) -> int:
    r = session.get(url, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"http {r.status_code} for {url}")
    body = r.content
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return len(body)


def worker_info(batch: list[str], threadlocal: threading.local, cookies: list[dict]) -> tuple[dict, str | None]:
    if not hasattr(threadlocal, "s"):
        threadlocal.s = make_session(cookies)
    try:
        return fetch_imageinfo_batch(threadlocal.s, batch), None
    except Exception as e:
        return {}, f"{type(e).__name__}: {e}"


def worker_download(task: tuple, threadlocal: threading.local, cookies: list[dict]) -> tuple[str, str, int, str | None]:
    """task = (bare_title, info_dict)."""
    bare_title, info = task
    if not hasattr(threadlocal, "s"):
        threadlocal.s = make_session(cookies)
    session = threadlocal.s
    url = info.get("url")
    sha = info.get("sha1") or hashlib.sha1(url.encode()).hexdigest()
    ext = ext_from_url_or_mime(url, info.get("mime") or "")
    dest = sha_to_local(sha, ext)
    expected_size = info.get("size") or 0
    if dest.exists() and (not expected_size or dest.stat().st_size == expected_size):
        return bare_title, "skip", 0, None
    try:
        n = download_one(session, url, dest)
    except Exception as e:
        return bare_title, "fail", 0, f"{type(e).__name__}: {e}"
    return bare_title, "ok", n, None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--concurrency", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv[1:])

    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} missing — run cookie_warmup_v2.py first")
        return 1
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    print(f"[plan] loaded {len(cookies)} cookies, concurrency={args.concurrency}")

    if not PARSED_DIR.exists():
        print(f"ERROR: {PARSED_DIR} missing")
        return 1

    print("[1/4] collect image titles from parsed/*")
    titles = collect_image_titles()
    if args.limit:
        titles = titles[: args.limit]

    manifest = load_manifest()
    todo = [t for t in titles if t not in manifest or manifest.get(t, {}).get("missing")]
    print(f"  [todo] {len(todo)} images (manifest has {len(manifest)} entries)")
    if not todo:
        return 0

    threadlocal = threading.local()
    t0 = time.time()

    print("[2/4] fetch imageinfo (batched) ...")
    info_map: dict[str, dict] = {}
    batches = [todo[i:i + IMAGEINFO_BATCH] for i in range(0, len(todo), IMAGEINFO_BATCH)]
    n_info_fail = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker_info, b, threadlocal, cookies): b for b in batches}
        done = 0
        for fut in as_completed(futures):
            out, err = fut.result()
            done += 1
            if err:
                n_info_fail += 1
                print(f"  [info {done}/{len(batches)}] FAIL: {err}")
            else:
                info_map.update(out)
            if done % 20 == 0:
                rate = done / (time.time() - t0)
                print(f"  [info {done}/{len(batches)}] rate={rate:.1f} batch/s, info_entries={len(info_map)}")
    print(f"  [info] {len(info_map)} entries resolved, {n_info_fail} batch failures")

    print("[3/4] downloading images concurrent ...")
    t1 = time.time()
    # Build download tasks (skip missing entries)
    tasks: list[tuple[str, dict]] = [
        (t, info) for t, info in info_map.items() if info and info.get("url") and not info.get("missing")
    ]
    print(f"  [dl] {len(tasks)} download tasks")
    total_bytes = 0
    n_ok = 0
    n_skip = 0
    n_fail = 0
    completed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(worker_download, t, threadlocal, cookies): t for t in tasks}
        for fut in as_completed(futures):
            bare, status, nbytes, err = fut.result()
            completed += 1
            if status == "ok":
                n_ok += 1
                total_bytes += nbytes
                info = info_map.get(bare, {})
                sha = info.get("sha1") or ""
                ext = ext_from_url_or_mime(info.get("url", ""), info.get("mime") or "")
                manifest[bare] = {
                    "sha1": sha, "ext": ext,
                    "local": f"{sha[:2]}/{sha[2:]}.{ext}",
                    "width": info.get("width"), "height": info.get("height"),
                    "size": info.get("size"), "mime": info.get("mime"),
                    "url": info.get("url"),
                }
            elif status == "skip":
                n_skip += 1
                info = info_map.get(bare, {})
                sha = info.get("sha1") or ""
                ext = ext_from_url_or_mime(info.get("url", ""), info.get("mime") or "")
                manifest[bare] = {
                    "sha1": sha, "ext": ext,
                    "local": f"{sha[:2]}/{sha[2:]}.{ext}",
                    "width": info.get("width"), "height": info.get("height"),
                    "size": info.get("size"), "mime": info.get("mime"),
                    "url": info.get("url"),
                }
            else:
                n_fail += 1
                manifest[bare] = {"missing": True, "error": err[:200] if err else ""}

            if completed % 100 == 0:
                save_manifest(manifest)
                elapsed = time.time() - t1
                rate = completed / max(elapsed, 0.001)
                eta_min = (len(tasks) - completed) / max(rate, 0.001) / 60
                bare_ascii = bare.encode("ascii", "replace").decode()[:30]
                print(f"  [dl {completed}/{len(tasks)}] ok={n_ok} skip={n_skip} fail={n_fail} "
                      f"bytes={total_bytes/1e6:.0f}MB rate={rate:.1f}/s eta={eta_min:.1f}min  {bare_ascii}",
                      flush=True)

    save_manifest(manifest)
    elapsed = time.time() - t1
    print(f"\n[4/4] done — ok={n_ok} skip={n_skip} fail={n_fail}, total={total_bytes/1e6:.0f} MB in {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
