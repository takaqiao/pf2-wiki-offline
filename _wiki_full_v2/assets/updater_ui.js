/* updater_ui.js — auto-update via incremental patch (preferred) or full ZIP.
 *
 * Robust invoke: Tauri 2 exposes invoke at different globals depending on
 * withGlobalTauri + version. We probe all known paths so the buttons work
 * regardless. All banner buttons use onclick→IPC (never bare <a> navigation,
 * which a WebView cannot turn into a file download).
 */
(function () {
  var REPO = 'takaqiao/pf2-wiki-offline';
  var API_URL = 'https://api.github.com/repos/' + REPO + '/releases/latest';
  var SNOOZE_KEY = 'pf2_updater_snoozed_tag';

  var CURRENT_VERSION = null;
  function loadCurrentVersion() {
    return fetch('/_app_version.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { return (j && j.version) ? j.version : null; })
      .catch(function () { return null; })
      .then(function (v) {
        if (v) { CURRENT_VERSION = v; return v; }
        var m = document.querySelector('meta[name="app-version"]');
        CURRENT_VERSION = (m && m.content) ? m.content : 'v0.3.12';
        return CURRENT_VERSION;
      });
  }

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

  // Probe every known Tauri 2 invoke location. Returns a fn(cmd,args)->Promise or null.
  function getInvoke() {
    try {
      if (window.__TAURI__ && window.__TAURI__.core && window.__TAURI__.core.invoke) {
        return window.__TAURI__.core.invoke.bind(window.__TAURI__.core);
      }
      if (window.__TAURI__ && window.__TAURI__.invoke) {
        return window.__TAURI__.invoke.bind(window.__TAURI__);
      }
      if (window.__TAURI_INTERNALS__ && window.__TAURI_INTERNALS__.invoke) {
        return window.__TAURI_INTERNALS__.invoke.bind(window.__TAURI_INTERNALS__);
      }
    } catch (e) {}
    return null;
  }
  function inTauri() { return getInvoke() !== null; }

  // Open a URL in the user's default browser (Tauri) or a new tab (browser).
  function openExternal(url) {
    var inv = getInvoke();
    if (inv) {
      inv('open_external', { url: url }).catch(function () {
        try { window.open(url, '_blank'); } catch (e) {}
      });
    } else {
      try { window.open(url, '_blank'); } catch (e) {}
    }
  }

  function showBanner(latest, patchInfo) {
    if (document.getElementById('pf2-updater-banner')) return;
    var releaseUrl = latest.html_url || ('https://github.com/' + REPO + '/releases/latest');
    var portableAsset = (latest.assets || []).find(function (a) {
      return /portable\.zip$/i.test(a.name);
    });
    var dlUrl = portableAsset ? portableAsset.browser_download_url : releaseUrl;
    var bodyText = (latest.body || '').split('\n')[0].slice(0, 120);

    var banner = document.createElement('div');
    banner.id = 'pf2-updater-banner';
    banner.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:99999',
      'background:#6d2002', 'color:#fffbf6', 'padding:10px 20px',
      'font:14px/1.4 "Helvetica Neue",Helvetica,Arial,sans-serif',
      'box-shadow:0 2px 8px rgba(0,0,0,0.3)', 'display:flex',
      'align-items:center', 'gap:12px', 'flex-wrap:wrap',
    ].join(';');

    var btnStyle = 'background:#ffb300;color:#3a1a00;border:0;padding:6px 16px;border-radius:3px;font-weight:600;cursor:pointer;font:inherit';
    var ghostStyle = 'background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.5);padding:6px 12px;border-radius:3px;cursor:pointer;font:inherit';

    // ALWAYS prefer the one-click patch button when a patch exists. We no longer
    // gate on isTauri() at render time — the click handler falls back gracefully.
    var primaryBtn;
    if (patchInfo) {
      primaryBtn = '<button id="pf2-updater-patch" style="' + btnStyle + '">一键自动更新 (' + Number(patchInfo.size_mb).toFixed(0) + ' MB)</button>';
    } else {
      primaryBtn = '<button id="pf2-updater-dl" style="' + btnStyle + '">下载完整版 (1.2 GB)</button>';
    }

    banner.innerHTML =
      '<div id="pf2-updater-msg" style="flex:1 1 auto;min-width:200px"><strong>有新版本：</strong> '
      + escapeHtml(CURRENT_VERSION || '?') + ' → ' + escapeHtml(latest.tag_name)
      + (bodyText ? ' — <span style="opacity:0.85">' + escapeHtml(bodyText) + '</span>' : '')
      + '</div>'
      + primaryBtn
      + '<button id="pf2-updater-full" style="' + ghostStyle + '">下载完整版</button>'
      + '<button id="pf2-updater-page" style="' + ghostStyle + '">看说明</button>'
      + '<button id="pf2-updater-dismiss" style="' + ghostStyle + '">本次忽略</button>';
    document.body.appendChild(banner);

    function on(id, fn) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('click', fn);
    }
    on('pf2-updater-dismiss', function () {
      try { localStorage.setItem(SNOOZE_KEY, latest.tag_name); } catch (e) {}
      banner.remove();
    });
    on('pf2-updater-full', function () { openExternal(dlUrl); });
    on('pf2-updater-page', function () { openExternal(releaseUrl); });
    on('pf2-updater-dl', function () { openExternal(dlUrl); });

    on('pf2-updater-patch', function () {
      var inv = getInvoke();
      if (!inv) {
        // Not in Tauri (or invoke unavailable) → open browser download instead
        openExternal(patchInfo.url || dlUrl);
        return;
      }
      var btn = document.getElementById('pf2-updater-patch');
      btn.disabled = true;
      btn.textContent = '下载中…';
      document.getElementById('pf2-updater-msg').innerHTML =
        '<strong>正在自动更新到 ' + escapeHtml(latest.tag_name) + '</strong> — 下载 ' + Number(patchInfo.size_mb).toFixed(0) + ' MB，完成后自动重启…';
      inv('apply_incremental_update', { url: patchInfo.url, expectedSha: patchInfo.sha256 })
        .catch(function (err) {
          btn.disabled = false;
          btn.textContent = '一键自动更新 (' + Number(patchInfo.size_mb).toFixed(0) + ' MB)';
          document.getElementById('pf2-updater-msg').innerHTML =
            '<strong style="color:#ffd0d0">自动更新失败</strong>: ' + escapeHtml(String(err)) + ' — 可点「下载完整版」手动升级';
        });
    });
  }

  function fetchPatchesJson(assets) {
    var a = (assets || []).find(function (x) { return x.name === 'patches.json'; });
    if (!a) return Promise.resolve(null);
    return fetch(a.browser_download_url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function check() {
    var snoozed = null;
    try { snoozed = localStorage.getItem(SNOOZE_KEY); } catch (e) {}
    loadCurrentVersion().then(function () {
      return fetch(API_URL, { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function (latest) {
        if (!latest || !latest.tag_name) return;
        if (cmpSemver(parseSemver(latest.tag_name), parseSemver(CURRENT_VERSION)) > 0
            && snoozed !== latest.tag_name) {
          return fetchPatchesJson(latest.assets).then(function (patches) {
            var patchInfo = (patches && patches.patches && patches.patches[CURRENT_VERSION]) || null;
            showBanner(latest, patchInfo);
          });
        }
      }).catch(function () {});
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(check, 2500); });
  } else {
    setTimeout(check, 2500);
  }
})();
