/* mw_collapsible.js — MediaWiki collapsible/foldable boxes for offline use.
 *
 * Replaces the standard mediawiki.toggle.collapsible module which we don't
 * load. Behavior:
 *   - .mw-collapsible           — element supports collapse
 *   - .mw-collapsed              — initially collapsed (defaults to expanded)
 *   - .mw-collapsible-toggle     — clickable toggle (auto-injected if missing)
 *   - .mw-collapsible-content    — content area shown/hidden by toggle
 *
 * For <table class="mw-collapsible">, the toggle goes into a new row at top.
 * For <div class="mw-collapsible">, toggle is positioned absolute top-right.
 *
 * Loaded via <script defer src="assets/mw_collapsible.js?v=v2e"> on every
 * built HTML page (build_v2/browse/classes/letters).
 */
(function () {
  function findContent(el) {
    var content = el.querySelector('.mw-collapsible-content');
    if (content) return content;
    // For <table>, content = tbody
    if (el.tagName === 'TABLE') return el.querySelector('tbody');
    return el;
  }

  function injectToggle(el) {
    // Skip if already has toggle injected
    if (el.querySelector(':scope > .mw-collapsible-toggle, :scope > * > .mw-collapsible-toggle')) return;

    var btn = document.createElement('a');
    btn.className = 'mw-collapsible-toggle';
    btn.setAttribute('role', 'button');
    btn.setAttribute('tabindex', '0');
    btn.href = '#';
    btn.style.cssText = 'cursor:pointer;user-select:none;font-size:12px;color:var(--link);margin-left:8px;font-weight:normal';

    var isCollapsed = el.classList.contains('mw-collapsed');
    btn.textContent = isCollapsed ? '[展开]' : '[折叠]';

    function toggle(e) {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      var nowCollapsed = el.classList.toggle('mw-collapsed');
      btn.textContent = nowCollapsed ? '[展开]' : '[折叠]';
      var content = findContent(el);
      if (content && content !== el) {
        content.style.display = nowCollapsed ? 'none' : '';
      } else {
        // For tables: hide all rows except first
        if (el.tagName === 'TABLE') {
          var rows = el.querySelectorAll('tbody > tr');
          for (var i = 1; i < rows.length; i++) {
            rows[i].style.display = nowCollapsed ? 'none' : '';
          }
        }
      }
    }
    btn.addEventListener('click', toggle);
    btn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') toggle(e);
    });

    // Position toggle:
    if (el.tagName === 'TABLE') {
      // For tables: into <caption> or first <th>
      var caption = el.querySelector(':scope > caption');
      if (caption) {
        caption.appendChild(btn);
      } else {
        var firstTh = el.querySelector(':scope > thead th, :scope > tbody > tr:first-child th');
        if (firstTh) firstTh.appendChild(btn);
        else {
          // Inject caption
          var cap = document.createElement('caption');
          cap.style.cssText = 'caption-side:top;text-align:right;padding:4px';
          cap.appendChild(btn);
          el.insertBefore(cap, el.firstChild);
        }
      }
    } else {
      // For div/section: prepend
      el.insertBefore(btn, el.firstChild);
    }

    // Apply initial collapsed state
    if (isCollapsed) {
      var content = findContent(el);
      if (content && content !== el) {
        content.style.display = 'none';
      } else if (el.tagName === 'TABLE') {
        var rows = el.querySelectorAll('tbody > tr');
        for (var i = 1; i < rows.length; i++) {
          rows[i].style.display = 'none';
        }
      }
    }
  }

  function init() {
    var els = document.querySelectorAll('.mw-collapsible');
    // mw-autocollapse: if >= 2 such elements on page, MediaWiki collapses them
    // all by default. We replicate that here so navbox-heavy pages (e.g. 战士)
    // don't render with 2-3 fully expanded 1000-row navboxes pushing content down.
    var autocollapse = document.querySelectorAll('.mw-collapsible.mw-autocollapse');
    if (autocollapse.length >= 2) {
      for (var j = 0; j < autocollapse.length; j++) {
        autocollapse[j].classList.add('mw-collapsed');
      }
    }
    for (var i = 0; i < els.length; i++) {
      try { injectToggle(els[i]); } catch (e) { console.error('[mw_collapsible] failed', e); }
    }
  }

  // Hamburger toggle for mobile (paired with _v2_compat.css .sidebar-hamburger)
  function setupHamburger() {
    if (window.innerWidth > 640) return;
    if (document.querySelector('.sidebar-hamburger')) return;
    var sidebar = document.querySelector('.wiki-sidebar');
    if (!sidebar) return;
    var btn = document.createElement('button');
    btn.className = 'sidebar-hamburger';
    btn.setAttribute('aria-label', '打开导航');
    btn.textContent = '☰';
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      document.body.classList.toggle('sidebar-open');
    });
    document.body.appendChild(btn);
    // Close on click overlay
    document.addEventListener('click', function (e) {
      if (document.body.classList.contains('sidebar-open') &&
          !sidebar.contains(e.target) && e.target !== btn) {
        document.body.classList.remove('sidebar-open');
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupHamburger);
  } else {
    setupHamburger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
