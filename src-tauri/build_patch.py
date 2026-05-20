"""Build incremental patch.zip — saves 95%+ download size on minor updates.

Compares two portable extract dirs (oldv vs newv) by sha256 per file, then
emits:
  - patch.zip — contains ALL files that were added or modified in newv
  - _patch_manifest.json (inside zip) — added/modified/removed lists, target
    versions, sha256s for verification

How users apply:
  1. Download `pf2-wiki-patch_<oldv>_to_<newv>.zip` from Release
  2. Stop pf2-wiki.exe (close window)
  3. Extract patch.zip into your portable folder (overwrite when prompted)
  4. If _patch_manifest.json lists "removed", delete those files manually
     (a short `_remove_these.txt` is included with the list)
  5. Restart pf2-wiki.exe — banner will detect the new version meta

Typical patch sizes (1.22 GB portable → patch):
  - CSS/JS-only changes: ~50 KB
  - +100 new pages: ~5 MB
  - +100 new images: ~50 MB
  - Major content refresh: ~100-200 MB (5-10x smaller than full ZIP)

Run:
  python build_patch.py --old <path-to-old-portable-dir> --new <path-to-new-portable-dir>
                        --out patch.zip --from-ver v0.3.7 --to-ver v0.3.8
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def walk_dir(root: Path) -> dict[str, str]:
    """Return {relative_path: sha256} for every file under root."""
    result = {}
    for f in root.rglob('*'):
        if not f.is_file():
            continue
        rel = f.relative_to(root).as_posix()
        try:
            result[rel] = sha256_of(f)
        except Exception as e:
            print(f'WARN sha failed: {rel}: {e}', file=sys.stderr)
    return result


def sha256_of_zip(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def write_patches_json(patches_json: Path, from_ver: str, to_ver: str,
                       patch_zip: Path, base_url: str) -> None:
    """Append one link to the version CHAIN in patches.json.

    Each release ships exactly one patch (previous→current); this records that
    single hop. The client walks the chain from its own version to `latest`,
    collecting the ordered list of patches to apply — "无数个小更新迭代".

    Schema:
      {
        "latest": "v0.3.20",
        "chain": {
          "v0.3.18": {"to": "v0.3.19", "url": "...", "sha256": "...", "size_mb": N},
          "v0.3.19": {"to": "v0.3.20", "url": "...", "sha256": "...", "size_mb": N}
        }
      }

    The chain is cumulative — old hops stay (their patch zips live in their own
    releases), so a client many versions behind can still chain up to latest.
    base_url is the NEW release's download URL prefix.
    """
    if patches_json.exists():
        try:
            data = json.loads(patches_json.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    else:
        data = {}
    # Migrate / drop any legacy flat 'patches' map.
    data.pop('patches', None)
    data.setdefault('chain', {})
    data['chain'][from_ver] = {
        'to': to_ver,
        'url': f'{base_url.rstrip("/")}/{patch_zip.name}',
        'sha256': sha256_of_zip(patch_zip),
        'size_mb': round(patch_zip.stat().st_size / 1024 / 1024, 2),
    }
    data['latest'] = to_ver
    patches_json.parent.mkdir(parents=True, exist_ok=True)
    patches_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )


def build_patch(old_dir: Path, new_dir: Path, out_zip: Path, from_ver: str, to_ver: str) -> None:
    print(f'[1/4] hashing OLD ({old_dir.name}) ...')
    old_hashes = walk_dir(old_dir)
    print(f'      {len(old_hashes):,} files')

    print(f'[2/4] hashing NEW ({new_dir.name}) ...')
    new_hashes = walk_dir(new_dir)
    print(f'      {len(new_hashes):,} files')

    added = []
    modified = []
    removed = []
    for path, h in new_hashes.items():
        if path not in old_hashes:
            added.append(path)
        elif old_hashes[path] != h:
            modified.append(path)
    for path in old_hashes:
        if path not in new_hashes:
            removed.append(path)

    print(f'[3/4] diff: +{len(added)} added  ~{len(modified)} modified  -{len(removed)} removed')

    manifest = {
        'patch_version': 1,
        'from_version': from_ver,
        'to_version': to_ver,
        'added': sorted(added),
        'modified': sorted(modified),
        'removed': sorted(removed),
        'sha256_after_apply': {p: new_hashes[p] for p in added + modified},
    }

    print(f'[4/4] writing {out_zip} ...')
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr('_patch_manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        if removed:
            remove_txt = '\n'.join(removed) + '\n'
            zf.writestr('_remove_these.txt', remove_txt)
        for path in sorted(added + modified):
            full = new_dir / path
            if full.is_file():
                zf.write(full, arcname=path)
    print(f'      patch size: {out_zip.stat().st_size / 1024 / 1024:.2f} MB')
    print(f'      vs full ZIP ~1220 MB → savings {(1 - out_zip.stat().st_size / (1220*1024*1024)) * 100:.1f}%')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--old', required=True, help='old portable extract dir')
    ap.add_argument('--new', required=True, help='new portable extract dir')
    ap.add_argument('--out', required=True, help='output patch.zip path')
    ap.add_argument('--from-ver', required=True, help='e.g. v0.3.7')
    ap.add_argument('--to-ver', required=True, help='e.g. v0.3.8')
    ap.add_argument('--patches-json', help='also write/merge patches.json next to out')
    ap.add_argument('--base-url', help='GitHub release download URL prefix '
                                       '(e.g. https://github.com/takaqiao/pf2-wiki-offline/releases/download/v0.3.8)')
    args = ap.parse_args()
    out = Path(args.out)
    build_patch(Path(args.old), Path(args.new), out, args.from_ver, args.to_ver)
    if args.patches_json and args.base_url:
        pj = Path(args.patches_json)
        write_patches_json(pj, args.from_ver, args.to_ver, out, args.base_url)
        print(f'  patches.json updated -> {pj}')


if __name__ == '__main__':
    main()
