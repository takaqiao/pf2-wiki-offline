/* keybindings.js — PF2 离线百科键盘快捷键
 *
 * Vanilla JS, no deps. Idempotent (safe to load twice).
 * Loaded via <script defer src="../assets/keybindings.js"> on every built page.
 *
 * Shortcuts (suppressed inside INPUT / TEXTAREA / contenteditable):
 *   Ctrl+K  /  /      → focus sidebar/topnav search input (fallback: navigate to search.html)
 *   Ctrl+L  /  T      → toggle dark / light theme (window.toggleTheme())
 *   Escape            → close banner (#pf2-updater-banner) / lightbox (.pf2-lightbox-overlay)
 *                       / our cheat-sheet modal / any open tooltip
 *   Alt+Left  /  B    → history.back()
 *   Alt+Right /  N    → history.forward()
 *   ?                 → open keybind cheat-sheet modal
 */
(function () {
  'use strict';

  if (window.__pf2KeybindingsLoaded) return;
  window.__pf2KeybindingsLoaded = true;

  var MODAL_ID = 'pf2-keybind-modal';
  var BANNER_ID = 'pf2-updater-banner';
  var LIGHTBOX_OVERLAY_SEL = '.pf2-lightbox-overlay, #pf2-lightbox-overlay, .pf2-lightbox';

  /* List that drives both behaviour and cheat-sheet rendering. */
  var BINDINGS = [
    { keys: ['Ctrl+K', '/'],     desc: '聚焦搜索框 / 跳转搜索页' },
    { keys: ['Ctrl+L', 'T'],     desc: '切换 暗黑 / 亮色 主题' },
    { keys: ['Esc'],             desc: '关闭弹窗 / 横幅 / 灯箱' },
    { keys: ['Alt+←', 'B'],      desc: '后退 (history.back)' },
    { keys: ['Alt+→', 'N'],      desc: '前进 (history.forward)' },
    { keys: ['?'],               desc: '显示本快捷键面板' },
  ];

  /* -------------------- Helpers -------------------- */

  function isEditable(el) {
    if (!el) return false;
    var tag = (el.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.isContentEditable) return true;
    // Walk up for contenteditable parents
    var p = el;
    while (p && p !== document.body) {
      if (p.getAttribute && p.getAttribute('contenteditable') === 'true') return true;
      p = p.parentNode;
    }
    return false;
  }

  function findSearchInput() {
    // Return the first VISIBLE search input. On mobile the topnav search box is
    // display:none — focusing it silently fails. Skip hidden inputs
    // (offsetParent === null) so the caller falls back to navigating to
    // search.html instead of a no-op.
    var sels = [
      '.topnav-search-input',
      '.sidebar .search-input',
      '.sidebar input[type="search"]',
      'input[type="search"]',
    ];
    for (var i = 0; i < sels.length; i++) {
      var els = document.querySelectorAll(sels[i]);
      for (var j = 0; j < els.length; j++) {
        if (els[j].offsetParent !== null) return els[j];
      }
    }
    return null;
  }

  function gotoSearch() {
    // Pages live in subdirs (pages/, data/, category/, source/, classes/) and the root.
    // Try ../search.html first, then ./search.html.
    var here = window.location.pathname;
    var target = (here.indexOf('/') === here.lastIndexOf('/')) ? 'search.html' : '../search.html';
    window.location.href = target;
  }

  function focusSearchOrGo() {
    var input = findSearchInput();
    if (input) {
      try { input.focus(); input.select && input.select(); } catch (e) { /* ignore */ }
      return;
    }
    gotoSearch();
  }

  function toggleTheme() {
    if (typeof window.toggleTheme === 'function') {
      window.toggleTheme();
      return;
    }
    // Fallback if theme.js hasn't loaded yet
    if (document.body) document.body.classList.toggle('dark');
  }

  function closeBanner() {
    var banner = document.getElementById(BANNER_ID);
    if (banner && banner.parentNode) {
      banner.parentNode.removeChild(banner);
      return true;
    }
    return false;
  }

  function closeLightbox() {
    var overlay = document.querySelector(LIGHTBOX_OVERLAY_SEL);
    if (overlay && overlay.parentNode) {
      overlay.parentNode.removeChild(overlay);
      if (document.body) document.body.style.overflow = '';
      return true;
    }
    return false;
  }

  function closeTooltips() {
    var killed = false;
    var tips = document.querySelectorAll(
      '.huiji-tooltip, .pf2-tooltip, .tooltip-popup, [data-pf2-tooltip-open="true"]'
    );
    for (var i = 0; i < tips.length; i++) {
      var t = tips[i];
      if (t.parentNode) {
        t.parentNode.removeChild(t);
        killed = true;
      }
    }
    return killed;
  }

  function closeModal() {
    var m = document.getElementById(MODAL_ID);
    if (m && m.parentNode) {
      m.parentNode.removeChild(m);
      return true;
    }
    return false;
  }

  /* -------------------- Cheat-sheet modal -------------------- */

  function openModal() {
    if (document.getElementById(MODAL_ID)) return; // already open

    var overlay = document.createElement('div');
    overlay.id = MODAL_ID;
    overlay.className = 'pf2-keybind-modal';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', MODAL_ID + '-title');

    var panel = document.createElement('div');
    panel.className = 'pf2-keybind-modal-panel';

    var title = document.createElement('h2');
    title.id = MODAL_ID + '-title';
    title.className = 'pf2-keybind-modal-title';
    title.textContent = '键盘快捷键';
    panel.appendChild(title);

    var list = document.createElement('dl');
    list.className = 'pf2-keybind-modal-list';
    for (var i = 0; i < BINDINGS.length; i++) {
      var b = BINDINGS[i];
      var dt = document.createElement('dt');
      for (var k = 0; k < b.keys.length; k++) {
        if (k > 0) {
          var sep = document.createElement('span');
          sep.className = 'pf2-keybind-or';
          sep.textContent = '或';
          dt.appendChild(sep);
        }
        var kbd = document.createElement('kbd');
        kbd.textContent = b.keys[k];
        dt.appendChild(kbd);
      }
      var dd = document.createElement('dd');
      dd.textContent = b.desc;
      list.appendChild(dt);
      list.appendChild(dd);
    }
    panel.appendChild(list);

    var hint = document.createElement('div');
    hint.className = 'pf2-keybind-modal-hint';
    hint.textContent = '按 Esc 关闭';
    panel.appendChild(hint);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'pf2-keybind-modal-close';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', function (e) {
      e.preventDefault();
      closeModal();
    });
    panel.appendChild(closeBtn);

    overlay.appendChild(panel);

    // Click on backdrop (not panel) closes
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });

    document.body.appendChild(overlay);
    try { closeBtn.focus(); } catch (e) { /* ignore */ }
  }

  /* -------------------- Key router -------------------- */

  function onKey(e) {
    // Always allow Escape to close overlays, even when typing in a search box
    if (e.key === 'Escape' || e.keyCode === 27) {
      // Try in order: modal → lightbox → banner → tooltip; stop at first hit
      if (closeModal() || closeLightbox() || closeBanner() || closeTooltips()) {
        e.preventDefault();
        return;
      }
      // If the active element is a search input, blur it as a soft-reset
      var ae = document.activeElement;
      if (ae && isEditable(ae) && ae.classList && ae.classList.contains('topnav-search-input')) {
        try { ae.blur(); } catch (_) { /* ignore */ }
        e.preventDefault();
      }
      return;
    }

    // All other shortcuts: suppress when typing
    if (isEditable(e.target) || isEditable(document.activeElement)) return;

    var key = e.key;
    var hasMod = e.ctrlKey || e.metaKey;
    var hasAlt = e.altKey;
    var hasShift = e.shiftKey;

    // Ctrl/Cmd + K → search focus
    if (hasMod && !hasAlt && (key === 'k' || key === 'K')) {
      e.preventDefault();
      focusSearchOrGo();
      return;
    }
    // Ctrl/Cmd + L → theme toggle (overrides browser address-bar shortcut by intent)
    if (hasMod && !hasAlt && (key === 'l' || key === 'L')) {
      e.preventDefault();
      toggleTheme();
      return;
    }
    // Alt + ArrowLeft → back
    if (hasAlt && key === 'ArrowLeft') {
      e.preventDefault();
      try { window.history.back(); } catch (_) { /* ignore */ }
      return;
    }
    // Alt + ArrowRight → forward
    if (hasAlt && key === 'ArrowRight') {
      e.preventDefault();
      try { window.history.forward(); } catch (_) { /* ignore */ }
      return;
    }

    // Single-letter / single-symbol shortcuts — only if no Ctrl/Alt/Meta
    if (hasMod || hasAlt) return;

    // "/" focuses search
    if (key === '/') {
      e.preventDefault();
      focusSearchOrGo();
      return;
    }
    // "?" opens cheat sheet (Shift+/ on most layouts)
    if (key === '?') {
      e.preventDefault();
      openModal();
      return;
    }
    // Single-letter shortcuts: ignore if Shift is held to avoid clobbering typing flows
    if (hasShift) return;
    if (key === 't' || key === 'T') { e.preventDefault(); toggleTheme(); return; }
    if (key === 'b' || key === 'B') { e.preventDefault(); try { window.history.back(); } catch (_) {} return; }
    if (key === 'n' || key === 'N') { e.preventDefault(); try { window.history.forward(); } catch (_) {} return; }
  }

  document.addEventListener('keydown', onKey, false);

  // Expose a tiny API for other scripts / tests
  window.pf2Keybindings = {
    openCheatSheet: openModal,
    closeCheatSheet: closeModal,
    bindings: BINDINGS.slice(),
  };
})();
