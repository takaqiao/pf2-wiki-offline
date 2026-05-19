/* updater_ui.js — listens for Tauri "update-available" event, shows a banner,
 * triggers download+install on click.
 *
 * Only runs in Tauri context (window.__TAURI_INTERNALS__ exists). No-op in
 * regular browser test.
 */
(function () {
  if (!window.__TAURI_INTERNALS__ || !window.__TAURI_INTERNALS__.invoke) {
    return;
  }

  function showBanner(info) {
    if (document.getElementById('pf2-updater-banner')) return;
    var banner = document.createElement('div');
    banner.id = 'pf2-updater-banner';
    banner.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:99999',
      'background:#6d2002', 'color:#fffbf6', 'padding:12px 20px',
      'font:14px/1.4 "Helvetica Neue",Helvetica,Arial,sans-serif',
      'box-shadow:0 2px 8px rgba(0,0,0,0.3)', 'display:flex',
      'align-items:center', 'gap:16px',
    ].join(';');
    banner.innerHTML =
      '<div style="flex:1 1 auto"><strong>更新可用：</strong> '
      + 'v' + (info.current_version || '?')
      + ' → v' + (info.new_version || '?')
      + (info.body ? ' — <span style="opacity:0.85">' + escapeHtml(info.body.slice(0, 120)) + '</span>' : '')
      + '</div>'
      + '<button id="pf2-updater-install" style="background:#ffb300;color:#3a1a00;border:0;padding:6px 16px;border-radius:3px;font-weight:600;cursor:pointer">立即更新</button>'
      + '<button id="pf2-updater-dismiss" style="background:transparent;color:#fffbf6;border:1px solid rgba(255,255,255,0.4);padding:6px 12px;border-radius:3px;cursor:pointer">稍后</button>';
    document.body.appendChild(banner);

    document.getElementById('pf2-updater-install').addEventListener('click', function () {
      var btn = this;
      btn.disabled = true;
      btn.textContent = '下载中…';
      window.__TAURI_INTERNALS__.invoke('install_update').catch(function (err) {
        btn.disabled = false;
        btn.textContent = '立即更新';
        alert('更新失败: ' + err);
      });
    });
    document.getElementById('pf2-updater-dismiss').addEventListener('click', function () {
      banner.remove();
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Listen for the Tauri event
  function listen() {
    if (window.__TAURI__ && window.__TAURI__.event && window.__TAURI__.event.listen) {
      window.__TAURI__.event.listen('update-available', function (e) {
        showBanner(e.payload || {});
      });
    } else if (window.__TAURI_INTERNALS__.transformCallback) {
      // Fallback: use lower-level invoke for listen
      var cb = window.__TAURI_INTERNALS__.transformCallback(function (payload) {
        showBanner(payload || {});
      });
      window.__TAURI_INTERNALS__.invoke('plugin:event|listen', {
        event: 'update-available',
        target: { kind: 'Any' },
        handler: cb,
      }).catch(function (err) {
        console.error('[updater_ui] listen failed:', err);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', listen);
  } else {
    listen();
  }
})();
