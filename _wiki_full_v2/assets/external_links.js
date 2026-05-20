/* external_links.js — open external <a href="http(s)://..."> in default browser.
 *
 * In Tauri context: invoke('open_external', {url}) → Rust opens via `open` crate.
 * In regular browser context (dev / Playwright QA): fallback to window.open.
 *
 * Loaded via <script defer src="assets/external_links.js?v=v2c"> on every built
 * HTML page (build_v2.py + build_browse_v2.py + build_class_hubs_v2.py +
 * build_browse_letters_v2.py).
 */
(function () {
  function isExternal(href) {
    if (!href) return false;
    if (!/^https?:\/\//i.test(href)) return false;
    if (href.indexOf('127.0.0.1') !== -1) return false;
    if (href.indexOf('localhost') !== -1) return false;
    return true;
  }

  // Probe all known Tauri 2 invoke locations (withGlobalTauri or internals).
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
      inv('open_external', { url: url }).catch(function (err) {
        console.error('[external_links] invoke failed:', err);
        try { window.open(url, '_blank', 'noopener,noreferrer'); } catch (e) {}
      });
    } else {
      try { window.open(url, '_blank', 'noopener,noreferrer'); } catch (e) {
        console.error('[external_links] window.open failed:', e);
      }
    }
  }

  function attach() {
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      var href = a.href || a.getAttribute('href') || '';
      if (!isExternal(href)) return;
      e.preventDefault();
      e.stopPropagation();
      openExternal(href);
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach);
  } else {
    attach();
  }
})();
