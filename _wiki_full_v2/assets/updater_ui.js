/* updater_ui.js — chained incremental auto-update.
 *
 * Each release ships ONE patch (previous→current). patches.json (read from
 * raw.githubusercontent.com, CORS-safe) holds the whole version chain:
 *   { "latest": "v0.3.20",
 *     "chain": { "v0.3.18": {to,url,sha256,size_mb}, "v0.3.19": {...}, ... } }
 * A client N versions behind walks the chain from its current version to
 * latest, collecting the ordered patch list, and applies them sequentially
 * via one IPC call ("无数个小更新迭代"). All buttons use onclick→IPC; the
 * one-click button shows only when a complete chain exists.
 */
(function () {
  var REPO = 'takaqiao/pf2-wiki-offline';
  var API_URL = 'https://api.github.com/repos/' + REPO + '/releases/latest';
  var PATCHES_URL = 'https://raw.githubusercontent.com/' + REPO + '/main/patches.json';
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
        CURRENT_VERSION = (m && m.content) ? m.content : 'v0.3.18';
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

  function fetchPatchesJson() {
    return fetch(PATCHES_URL + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  // Walk the chain from `current` to `latestTag`. Returns
  //   { steps: [{url,sha256,size_mb,to}], totalMb, count }  on a complete chain,
  //   or null if no chain (or it doesn't reach latest → caller offers full ZIP).
  function buildChain(patches, current, latestTag) {
    if (!patches || !patches.chain) return null;
    var steps = [];
    var v = current;
    var guard = 0;
    while (patches.chain[v] && guard++ < 100) {
      var step = patches.chain[v];
      steps.push(step);
      v = step.to;
      if (v === latestTag) break;
    }
    if (!steps.length || v !== latestTag) return null;
    var totalMb = steps.reduce(function (s, p) { return s + (Number(p.size_mb) || 0); }, 0);
    return { steps: steps, totalMb: totalMb, count: steps.length };
  }

  function showBanner(latest, chain) {
    if (document.getElementById('pf2-updater-banner')) return;
    var releaseUrl = latest.html_url || ('https://github.com/' + REPO + '/releases/latest');
    var portableAsset = (latest.assets || []).find(function (a) {
      return /portable\.zip$/i.test(a.name);
    });
    var dlUrl = portableAsset ? portableAsset.browser_download_url : releaseUrl;
    var bodyText = (latest.body || '').split('\n')[0].slice(0, 110);

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

    var patchLabel = '';
    if (chain) {
      patchLabel = '一键自动更新 ('
        + (chain.count > 1 ? chain.count + ' 个补丁 · ' : '')
        + (chain.totalMb < 1 ? '<1' : chain.totalMb.toFixed(1)) + ' MB)';
    }
    var primaryBtn = chain
      ? '<button id="pf2-updater-patch" style="' + btnStyle + '">' + patchLabel + '</button>'
      : '';
    var fullStyle = chain ? ghostStyle : btnStyle;

    banner.innerHTML =
      '<div id="pf2-updater-msg" style="flex:1 1 auto;min-width:200px"><strong>有新版本：</strong> '
      + escapeHtml(CURRENT_VERSION || '?') + ' → ' + escapeHtml(latest.tag_name)
      + (bodyText ? ' — <span style="opacity:0.85">' + escapeHtml(bodyText) + '</span>' : '')
      + '</div>'
      + primaryBtn
      + '<button id="pf2-updater-full" style="' + fullStyle + '">下载完整版 (1.2 GB)</button>'
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

    on('pf2-updater-patch', function () {
      var inv = getInvoke();
      if (!inv) { openExternal(dlUrl); return; }
      var btn = document.getElementById('pf2-updater-patch');
      btn.disabled = true;
      btn.textContent = '下载中…';
      document.getElementById('pf2-updater-msg').innerHTML =
        '<strong>正在更新到 ' + escapeHtml(latest.tag_name) + '</strong> — '
        + chain.count + ' 个补丁，完成后自动重启…';
      var payload = chain.steps.map(function (s) { return { url: s.url, sha256: s.sha256 }; });
      inv('apply_incremental_update', { patches: payload })
        .catch(function (err) {
          btn.disabled = false;
          btn.textContent = patchLabel;
          document.getElementById('pf2-updater-msg').innerHTML =
            '<strong style="color:#ffd0d0">自动更新失败</strong>: ' + escapeHtml(String(err)) + ' — 可点「下载完整版」手动升级';
        });
    });
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
          return fetchPatchesJson().then(function (patches) {
            var chain = buildChain(patches, CURRENT_VERSION, latest.tag_name);
            showBanner(latest, chain);
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
