/* updater_ui.js — chained incremental auto-update (client-driven).
 *
 * Each release ships ONE patch (previous→current). patches.json (read from
 * raw.githubusercontent.com, CORS-safe) holds the whole version chain:
 *   { "latest": "v0.3.22",
 *     "chain": { "v0.3.18": {to,url,sha256,size_mb}, "v0.3.19": {...}, ... } }
 * A client N versions behind walks the chain from its current version to
 * latest, collecting the ordered patch list, and applies them sequentially
 * via one IPC call ("无数个小更新迭代").
 *
 * Detection AND the chain both come from patches.json. The GitHub REST API is
 * intentionally NOT used: it is rate-limited (60 req/h unauth — blown fast by
 * per-page-load checks) and often blocked/throttled behind the GFW, which would
 * silently kill update detection. Banner URLs are derived from the release
 * naming convention instead. Network is throttled and patches.json is cached so
 * the banner still shows between checks.
 */
(function () {
  var REPO = 'takaqiao/pf2-wiki-offline';
  var PATCHES_URL = 'https://raw.githubusercontent.com/' + REPO + '/main/patches.json';
  var SNOOZE_KEY = 'pf2_updater_snoozed_tag';
  var THROTTLE_KEY = 'pf2_updater_last_check';
  var PATCHES_CACHE_KEY = 'pf2_updater_patches_cache';
  var THROTTLE_MS = 6 * 60 * 60 * 1000; // re-hit network at most every 6h

  function fullZipUrl(tag) {
    var ver = String(tag).replace(/^v/, '');
    return 'https://github.com/' + REPO + '/releases/download/' + tag
      + '/pf2-wiki-offline_' + ver + '_x64-portable.zip';
  }
  function releasePageUrl(tag) {
    return 'https://github.com/' + REPO + '/releases/tag/' + tag;
  }

  var CURRENT_VERSION = null;
  function loadCurrentVersion() {
    return fetch('/_app_version.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { return (j && j.version) ? j.version : null; })
      .catch(function () { return null; })
      .then(function (v) {
        // If version is unknown, leave it null so decide() suppresses the banner
        // (a hardcoded fallback could show a spurious "update available" prompt).
        CURRENT_VERSION = v || null;
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

  // Tauri 2 event listener (for update-progress events from apply_incremental_update).
  function getListen() {
    try {
      if (window.__TAURI__ && window.__TAURI__.event && window.__TAURI__.event.listen) {
        return window.__TAURI__.event.listen.bind(window.__TAURI__.event);
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

  // latestTag: string like "v0.3.22". chain: result of buildChain or null.
  function showBanner(latestTag, chain) {
    if (document.getElementById('pf2-updater-banner')) return;
    var releaseUrl = releasePageUrl(latestTag);
    var dlUrl = fullZipUrl(latestTag);

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
      + escapeHtml(CURRENT_VERSION || '?') + ' → ' + escapeHtml(latestTag)
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
      try { localStorage.setItem(SNOOZE_KEY, latestTag); } catch (e) {}
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
        '<strong>正在更新到 ' + escapeHtml(latestTag) + '</strong>'
        + '<div style="margin-top:6px;height:8px;border-radius:4px;background:rgba(0,0,0,.18);overflow:hidden">'
        + '<div id="pf2-upd-fill" style="height:100%;width:0%;background:#ffb300;transition:width .15s"></div></div>'
        + '<div id="pf2-upd-pct" style="margin-top:4px;font-size:12px;opacity:.85">准备中…</div>';

      // Listen for download/verify/apply progress so the user sees a percentage.
      // Attach exactly once per page (a retry after error must not double-register).
      var lis = getListen();
      if (lis && !window.__pf2UpdProgressBound) {
        window.__pf2UpdProgressBound = true;
        lis('update-progress', function (ev) {
          var p = (ev && ev.payload) || {};
          var fill = document.getElementById('pf2-upd-fill');
          var pct = document.getElementById('pf2-upd-pct');
          if (!fill || !pct) return;
          if (p.phase === 'download') {
            if (p.total) {
              fill.style.width = (p.pct || 0) + '%';
              pct.textContent = '下载补丁 ' + p.patch + '/' + p.total_patches + ' — ' + (p.pct || 0)
                + '% (' + (p.downloaded / 1048576).toFixed(1) + ' / ' + (p.total / 1048576).toFixed(1) + ' MB)';
            } else {
              // unknown total: indeterminate — show bytes, keep bar pulsing-ish
              fill.style.width = '40%';
              pct.textContent = '下载补丁 ' + p.patch + '/' + p.total_patches + ' — ' + (p.downloaded / 1048576).toFixed(1) + ' MB';
            }
          } else if (p.phase === 'verify') {
            fill.style.width = '100%';
            pct.textContent = '校验补丁 ' + p.patch + '/' + p.total_patches + '…';
          } else if (p.phase === 'apply') {
            fill.style.width = '100%';
            pct.textContent = '正在应用更新，即将自动重启…';
          }
        }).catch(function () {});
      }

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

  function decide(patches) {
    if (!patches || !patches.latest) return;
    if (!CURRENT_VERSION) return;  // unknown local version -> never prompt
    var latestTag = patches.latest;
    var snoozed = null;
    try { snoozed = localStorage.getItem(SNOOZE_KEY); } catch (e) {}
    if (cmpSemver(parseSemver(latestTag), parseSemver(CURRENT_VERSION)) > 0
        && snoozed !== latestTag) {
      showBanner(latestTag, buildChain(patches, CURRENT_VERSION, latestTag));
    }
  }

  function check() {
    loadCurrentVersion().then(function () {
      var last = 0, cached = null;
      try { last = +(localStorage.getItem(THROTTLE_KEY) || 0); } catch (e) {}
      try { cached = JSON.parse(localStorage.getItem(PATCHES_CACHE_KEY) || 'null'); } catch (e) {}

      // Within the throttle window: decide from cache, no network call.
      if (cached && (Date.now() - last) < THROTTLE_MS) { decide(cached); return; }

      fetchPatchesJson().then(function (patches) {
        if (patches) {
          try {
            localStorage.setItem(THROTTLE_KEY, String(Date.now()));
            localStorage.setItem(PATCHES_CACHE_KEY, JSON.stringify(patches));
          } catch (e) {}
        } else {
          patches = cached; // network failed → fall back to last cached chain
        }
        decide(patches);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(check, 2500); });
  } else {
    setTimeout(check, 2500);
  }
})();
