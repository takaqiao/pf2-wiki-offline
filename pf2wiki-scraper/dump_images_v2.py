"""Phase C: download all referenced images locally.

Reads parsed/* JSON, extracts all image titles from parse.images[],
batches imageinfo, downloads originalurl + a few common thumb sizes.

Output:
  out_v2/images/<sha1[:2]>/<sha1[2:]>.<ext>           original
  out_v2/images/manifest.json {"File:X": {sha1, ext, w, h, mime, url, local}}

Re-runnable: skips images already present in manifest.

Run:
    .venv\\Scripts\\python.exe dump_images_v2.py          # full
    .venv\\Scripts\\python.exe dump_images_v2.py --limit 100
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

from pfwiki import api_get, browser

ROOT = Path(__file__).resolve().parent
OUT_V2 = ROOT / "out_v2"
PARSED_DIR = OUT_V2 / "parsed"
IMAGES_DIR = OUT_V2 / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_FILE = IMAGES_DIR / "manifest.json"
STATE_FILE = IMAGES_DIR / "_state.json"

# Batch size for imageinfo prop query — MW caps titles= at 50 per request for anons
IMAGEINFO_BATCH = 50


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def save_manifest(m: dict) -> None:
    MANIFEST_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_image_titles() -> list[str]:
    """Scan parsed/* JSON for all unique image references."""
    seen: set[str] = set()
    n_files = 0
    for sub in PARSED_DIR.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sub.iterdir():
            if not f.suffix == ".json":
                continue
            n_files += 1
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            for img in (doc.get("parse") or {}).get("images", []) or []:
                # parse.images entries are filenames (without "File:" prefix typically)
                seen.add(img)
    print(f"  [collect] scanned {n_files} parsed files, {len(seen)} unique image titles")
    return sorted(seen)


def sha_to_local(sha1: str, ext: str) -> Path:
    return IMAGES_DIR / sha1[:2] / f"{sha1[2:]}.{ext}"


def ext_from_url_or_mime(url: str, mime: str) -> str:
    # Try URL suffix first
    path = unquote(urlparse(url).path)
    if "." in path:
        e = path.rsplit(".", 1)[-1].lower()
        # Sanitize — keep only known safe extensions
        if e in {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "tiff", "ico", "pdf"}:
            return e
    # Fallback to mime
    m = mime.lower() if mime else ""
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


def fetch_imageinfo_batch(page, titles: list[str]) -> dict:
    """One imageinfo batch. Returns dict title->info."""
    titles_param = "|".join(f"File:{t}" if not t.startswith("File:") else t for t in titles)
    params = {
        "action": "query",
        "titles": titles_param,
        "prop": "imageinfo",
        "iiprop": "url|size|sha1|mime|timestamp",
        "format": "json",
        "formatversion": "2",
    }
    result = api_get(page, params)
    out: dict[str, dict] = {}
    for p in (result.get("query") or {}).get("pages", []) or []:
        title = p.get("title", "")
        # Strip "File:" prefix to match input
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


def download_image(page, url: str, dest: Path) -> int:
    """Download URL via the playwright request context. Returns bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = page.request.get(url, timeout=30000)
    if resp.status != 200:
        raise RuntimeError(f"status {resp.status} for {url}")
    body = resp.body()
    dest.write_bytes(body)
    return len(body)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rate", type=float, default=2.0)
    args = ap.parse_args(argv[1:])

    if not PARSED_DIR.exists() or not any(PARSED_DIR.iterdir()):
        print(f"ERROR: {PARSED_DIR} empty — run dump_parsed_v2.py first")
        return 1

    print("[1/4] collect image titles from parsed/*")
    titles = collect_image_titles()
    if args.limit:
        titles = titles[: args.limit]

    manifest = load_manifest()
    print(f"  [manifest] {len(manifest)} entries already present")

    todo = [t for t in titles if t not in manifest or "missing" in manifest.get(t, {})]
    print(f"  [todo] {len(todo)} images to fetch info + download")
    if not todo:
        print("[done] nothing to do")
        return 0

    min_interval = 1.0 / max(args.rate, 0.1)
    t0 = time.time()
    total_bytes = 0

    with browser(headless=False) as (_ctx, page):
        print("[2/4] imageinfo batches ...")
        info_map: dict[str, dict] = {}
        for i in range(0, len(todo), IMAGEINFO_BATCH):
            batch = todo[i:i + IMAGEINFO_BATCH]
            t1 = time.time()
            try:
                info = fetch_imageinfo_batch(page, batch)
            except Exception as e:
                print(f"  [info-batch {i//IMAGEINFO_BATCH+1}] FAIL: {e}")
                continue
            info_map.update(info)
            since = time.time() - t1
            if since < min_interval:
                time.sleep(min_interval - since)
            if (i // IMAGEINFO_BATCH) % 10 == 0:
                print(f"  [info] batch {i//IMAGEINFO_BATCH+1}/{(len(todo)+IMAGEINFO_BATCH-1)//IMAGEINFO_BATCH} (+{len(info)})")

        print(f"  [info] resolved {len(info_map)} entries")

        print("[3/4] downloading images ...")
        downloaded = 0
        last_req = 0.0
        for i, (bare_title, info) in enumerate(info_map.items()):
            if info.get("missing"):
                manifest[bare_title] = {"missing": True}
                continue
            url = info.get("url")
            sha = info.get("sha1") or hashlib.sha1(url.encode()).hexdigest()
            ext = ext_from_url_or_mime(url, info.get("mime") or "")
            dest = sha_to_local(sha, ext)

            if dest.exists() and dest.stat().st_size == (info.get("size") or 0):
                manifest[bare_title] = {
                    "sha1": sha, "ext": ext, "local": str(dest.relative_to(IMAGES_DIR)),
                    "width": info.get("width"), "height": info.get("height"),
                    "size": info.get("size"), "mime": info.get("mime"),
                    "url": url,
                }
                continue

            since = time.time() - last_req
            if since < min_interval:
                time.sleep(min_interval - since)

            try:
                n = download_image(page, url, dest)
                total_bytes += n
                downloaded += 1
            except Exception as e:
                print(f"  [{i+1}/{len(info_map)}] DL FAIL {bare_title[:40]}: {e}")
                manifest[bare_title] = {"missing": True, "error": str(e)[:200]}
                last_req = time.time()
                continue

            last_req = time.time()
            manifest[bare_title] = {
                "sha1": sha, "ext": ext, "local": str(dest.relative_to(IMAGES_DIR)),
                "width": info.get("width"), "height": info.get("height"),
                "size": info.get("size"), "mime": info.get("mime"),
                "url": url,
            }
            # Periodic flush
            if (i + 1) % 50 == 0:
                save_manifest(manifest)
                elapsed = time.time() - t0
                rate = downloaded / max(elapsed, 0.001)
                eta = (len(info_map) - i - 1) / max(rate, 0.01)
                bare_ascii = bare_title.encode("ascii", "replace").decode()[:40]
                print(f"  [{i+1}/{len(info_map)}] dl={downloaded} bytes={total_bytes/1e6:.0f}MB "
                      f"rate={rate:.2f}/s eta={eta/60:.1f}min  {bare_ascii}")

        save_manifest(manifest)
        print(f"\n[4/4] done — downloaded={downloaded}, total={total_bytes/1e6:.0f} MB in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
