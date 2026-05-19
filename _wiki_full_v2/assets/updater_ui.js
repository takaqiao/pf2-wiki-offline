/* updater_ui.js — check GitHub Releases for newer version + show banner.
 *
 * Works in both Tauri (portable & NSIS) and regular browser preview. Since the
 * Tauri plugin-updater requires a working NSIS/MSI installer (which we don't
 * ship anymore — 2 GB upstream limit), we switched to a banner + manual link
 * to the Releases page. Users click → browser opens → download new ZIP.
 *
 * Detection: fetch GitHub Releases API "latest", compare tag_name to the
 * version embedded in document. Stores "snoozed" dismissal in localStorage.
 */
(function () {
  var REPO = 'takaqiao/pf2-wiki-offline';
  var API_URL = 'https://api.github.com/repos/' + REPO + '/releases/latest';
  var SNOOZE_KEY = 'pf2_updater_snoozed_tag';
  // Read current version from <meta name="app-version" content="v0.3.7">
  // build_v2.py injects this into every page.
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

  function showBanner(latest) {
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
    banner.innerHTML =
      '<div style="flex:1 1 auto;min-width:220px"><strong>有新版本：</strong> '
      + escapeHtml(CURRENT_VERSION) + ' → ' + escapeHtml(latest.tag_name)
      + (bodyText ? ' — <span style="opacity:0.85">' + escapeHtml(bodyText) + '</span>' : '')
      + '</div>'
      + '<a id="pf2-updater-dl" href="' + escapeHtml(dlUrl) + '" rel="external" style="background:#ffb300;color:#3a1a00;border:0;padding:6px 16px;border-radius:3px;font-weight:600;text-decoration:none">下载新版</a>'
      + '<a id="pf2-updater-page" href="' + escapeHtml(releaseUrl) + '" rel="external" style="background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.5);padding:6px 12px;border-radius:3px;text-decoration:none">看说明</a>'
      + '<button id="pf2-updater-dismiss" style="background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.4);padding:6px 12px;border-radius:3px;cursor:pointer">本次忽略</button>';
    document.body.appendChild(banner);

    document.getElementById('pf2-updater-dismiss').addEventListener('click', function () {
      try { localStorage.setItem(SNOOZE_KEY, latest.tag_name); } catch (e) {}
      banner.remove();
    });
  }

  function check() {
    // Don't pop again if already snoozed for this exact tag
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
        showBanner(latest);
      }
    }).catch(function (err) {
      // network failure (offline use case) — silent fail, no banner
      // console.debug('[updater] skip:', err);
    });
  }

  // Run after a brief delay so initial render isn't blocked
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(check, 3000); });
  } else {
    setTimeout(check, 3000);
  }
})();
