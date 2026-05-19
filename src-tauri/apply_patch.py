"""Apply an incremental patch.zip to a PF2 离线百科 portable install.

For end users:
  1. Stop pf2-wiki.exe (close window)
  2. Drop patch.zip in same folder as pf2-wiki.exe
  3. Double-click apply_patch.exe (or run: python apply_patch.py)
  4. Restart pf2-wiki.exe

Or distribute compiled via PyInstaller. For now, runnable as Python script.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def apply_patch(patch_zip: Path, install_dir: Path) -> int:
    if not patch_zip.exists():
        print(f'ERROR: patch zip not found: {patch_zip}')
        return 1
    if not install_dir.exists():
        print(f'ERROR: install dir not found: {install_dir}')
        return 1

    with zipfile.ZipFile(patch_zip, 'r') as zf:
        if '_patch_manifest.json' not in zf.namelist():
            print('ERROR: not a valid patch (no _patch_manifest.json)')
            return 2
        manifest = json.loads(zf.read('_patch_manifest.json').decode('utf-8'))

        print(f'  patch: {manifest["from_version"]} -> {manifest["to_version"]}')
        print(f'  add: {len(manifest["added"])}  modify: {len(manifest["modified"])}  remove: {len(manifest["removed"])}')

        # Extract added + modified
        for path in manifest['added'] + manifest['modified']:
            target = install_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(path) as src, target.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            # Verify sha
            expected_sha = manifest['sha256_after_apply'].get(path)
            if expected_sha:
                actual = sha256_of(target)
                if actual != expected_sha:
                    print(f'WARN: sha mismatch on {path}; got {actual[:8]}, expected {expected_sha[:8]}')

    # Delete removed files
    for path in manifest['removed']:
        target = install_dir / path
        if target.exists():
            try:
                target.unlink()
            except Exception as e:
                print(f'WARN: failed to delete {path}: {e}')

    print(f'OK — install dir updated to {manifest["to_version"]}')
    return 0


def main():
    if len(sys.argv) >= 2:
        patch_zip = Path(sys.argv[1])
    else:
        # Auto-find patch.zip in same dir as this script / exe
        here = Path(__file__).resolve().parent if '__file__' in globals() else Path('.')
        candidates = list(here.glob('pf2-wiki-patch_*.zip'))
        if not candidates:
            print('Usage: python apply_patch.py <patch.zip>')
            print('Or put patch.zip in same folder as this script')
            sys.exit(1)
        patch_zip = candidates[0]
        print(f'auto-detected patch: {patch_zip.name}')

    install_dir = Path(__file__).resolve().parent if '__file__' in globals() else Path('.')
    print(f'applying to: {install_dir}')
    sys.exit(apply_patch(patch_zip, install_dir))


if __name__ == '__main__':
    main()
