/* updater_ui.js — auto-update via incremental patch (preferred) or full ZIP.
 *
 * Flow:
 * 1. Fetch GitHub Releases API "latest"
 * 2. Compare tag_name to <meta name="app-version">
 * 3. If newer:
 *    a. Look for `patches.json` asset → check if a patch exists for current→latest
 *    b. If patch available AND running inside Tauri → show "一键自动更新" button
 *       (Rust IPC downloads patch.zip, verifies sha256, runs update.ps1 detached, exits app)
 *    c. Else → show "下载完整 portable" button (browser opens release URL)
 *
 * Patches.json schema (placed in release alongside portable.zip):
 *   {
 *     "patches": {
 *       "v0.3.7": {
 *         "url": "https://github.com/.../pf2-wiki-patch_v0.3.7_to_v0.3.8.zip",
 *         "sha256": "abc123...",
 *         "size_mb": 35.5
 *       }
 *     }
 *   }
 */
(function () {
  var REPO = 'takaqiao/pf2-wiki-offline';
  var API_URL = 'https://api.github.com/repos/' + REPO + '/releases/latest';
  var SNOOZE_KEY = 'pf2_updater_snoozed_tag';

  function getCurrentVersion() {
    var m = document.querySelector('meta[name="app-version"]');
    return (m && m.content) ? m.content : 'v0.3.7';
  }
  var CURRENT_VERSION = getCurrentVersion();

  function parseSemver(s) {
    if (!s) return null;
    var m = String(s).replace(/^v/, '').match(/^(\d+)\.(\d+)\.(\d+)/);
    if (!m) return null;
    return [+m[1], +m[2], +m[3]];
  }
  function cmpSemver(a, b) {
    if (!a || !b) return 0;
    for (var i = 0; i < 3; i++) { if (a[i] !== b[i]) return a[i] - b[i]; }
    return 0;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function isTauri() {
    return !!(window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke);
  }

  function invoke(cmd, args) {
    if (!isTauri()) return Promise.reject(new Error('not in Tauri'));
    return window.__TAURI_INTERNALS__.invoke(cmd, args);
  }

  function showBanner(latest, patchInfo) {
    if (document.getElementById('pf2-updater-banner')) return;
    var releaseUrl = latest.html_url || ('https://github.com/' + REPO + '/releases/latest');
    var portableAsset = (latest.assets || []).find(function (a) {
      return /portable\.zip$/i.test(a.name);
    });
    var dlUrl = portableAsset ? portableAsset.browser_download_url : releaseUrl;
    var bodyText = (latest.body || '').split('\n')[0].slice(0, 140);

    var banner = document.createElement('div');
    banner.id = 'pf2-updater-banner';
    banner.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:99999',
      'background:#6d2002', 'color:#fffbf6', 'padding:10px 20px',
      'font:14px/1.4 "Helvetica Neue",Helvetica,Arial,sans-serif',
      'box-shadow:0 2px 8px rgba(0,0,0,0.3)', 'display:flex',
      'align-items:center', 'gap:14px', 'flex-wrap:wrap',
    ].join(';');

    var btnHtml = '';
    if (patchInfo && isTauri()) {
      // 一键自动更新: Rust IPC
      btnHtml = '<button id="pf2-updater-patch" style="background:#ffb300;color:#3a1a00;border:0;padding:6px 16px;border-radius:3px;font-weight:600;cursor:pointer">一键自动更新 (' + patchInfo.size_mb.toFixed(0) + ' MB)</button>';
    } else {
      btnHtml = '<a id="pf2-updater-dl" href="' + escapeHtml(dlUrl) + '" rel="external" style="background:#ffb300;color:#3a1a00;border:0;padding:6px 16px;border-radius:3px;font-weight:600;text-decoration:none">下载完整版 (1.2 GB)</a>';
    }

    banner.innerHTML =
      '<div id="pf2-updater-msg" style="flex:1 1 auto;min-width:220px"><strong>有新版本：</strong> '
      + escapeHtml(CURRENT_VERSION) + ' → ' + escapeHtml(latest.tag_name)
      + (bodyText ? ' — <span style="opacity:0.85">' + escapeHtml(bodyText) + '</span>' : '')
      + '</div>'
      + btnHtml
      + '<a id="pf2-updater-page" href="' + escapeHtml(releaseUrl) + '" rel="external" style="background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.5);padding:6px 12px;border-radius:3px;text-decoration:none">看说明</a>'
      + '<button id="pf2-updater-dismiss" style="background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.4);padding:6px 12px;border-radius:3px;cursor:pointer">本次忽略</button>';
    document.body.appendChild(banner);

    document.getElementById('pf2-updater-dismiss').addEventListener('click', function () {
      try { localStorage.setItem(SNOOZE_KEY, latest.tag_name); } catch (e) {}
      banner.remove();
    });

    var patchBtn = document.getElementById('pf2-updater-patch');
    if (patchBtn) {
      patchBtn.addEventListener('click', function () {
        patchBtn.disabled = true;
        patchBtn.textContent = '下载中…';
        document.getElementById('pf2-updater-msg').innerHTML =
          '<strong>正在自动更新到 ' + escapeHtml(latest.tag_name) + '</strong> — 完成后会自动重启';
        invoke('apply_incremental_update', {
          url: patchInfo.url,
          expectedSha: patchInfo.sha256,
        }).catch(function (err) {
          patchBtn.disabled = false;
          patchBtn.textContent = '一键自动更新 (' + patchInfo.size_mb.toFixed(0) + ' MB)';
          alert('自动更新失败: ' + err + '\n\n请点"下载完整版"手动升级。');
        });
      });
    }
  }

  function fetchPatchesJson(assets) {
    var patchesAsset = (assets || []).find(function (a) {
      return a.name === 'patches.json';
    });
    if (!patchesAsset) return Promise.resolve(null);
    return fetch(patchesAsset.browser_download_url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function check() {
    var snoozed = null;
    try { snoozed = localStorage.getItem(SNOOZE_KEY); } catch (e) {}

    fetch(API_URL, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('http ' + r.status);
      return r.json();
    }).then(function (latest) {
      if (!latest || !latest.tag_name) return;
      var a = parseSemver(CURRENT_VERSION);
      var b = parseSemver(latest.tag_name);
      if (cmpSemver(b, a) > 0 && snoozed !== latest.tag_name) {
        // Check for patch
        return fetchPatchesJson(latest.assets).then(function (patches) {
          var patchInfo = null;
          if (patches && patches.patches && patches.patches[CURRENT_VERSION]) {
            patchInfo = patches.patches[CURRENT_VERSION];
          }
          showBanner(latest, patchInfo);
        });
      }
    }).catch(function (err) {
      // network failure (offline use case) — silent fail
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(check, 3000); });
  } else {
    setTimeout(check, 3000);
  }
})();
