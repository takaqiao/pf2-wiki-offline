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
    // INT-1: tables have no single content wrapper — collapsing is handled
    // row-by-row in applyCollapsedState() so the title row stays visible.
    // (Returning tbody here used to hide the title row + toggle with it.)
    if (el.tagName === 'TABLE') return null;
    return el;
  }

  // Direct rows of a table (inside its own thead/tbody/tfoot, or stray
  // <tr> children), excluding rows of nested tables (navbox-subgroup etc.).
  function getDirectRows(table) {
    var rows = [];
    for (var sec = table.firstElementChild; sec; sec = sec.nextElementSibling) {
      if (sec.tagName === 'TBODY' || sec.tagName === 'THEAD' || sec.tagName === 'TFOOT') {
        for (var r = sec.firstElementChild; r; r = r.nextElementSibling) {
          if (r.tagName === 'TR') rows.push(r);
        }
      } else if (sec.tagName === 'TR') {
        rows.push(sec);
      }
    }
    return rows;
  }

  /* Apply collapsed/expanded state. Replicates MediaWiki
   * jquery.makeCollapsible:
   *   - explicit .mw-collapsible-content → show/hide that wrapper;
   *   - TABLE (INT-1) → hide/show every direct row EXCEPT the row holding
   *     the toggle (first row when no caption). <caption> and the title
   *     row are therefore always visible; with a caption-hosted toggle all
   *     rows hide but the caption (with the toggle) remains. */
  function applyCollapsedState(el, btn, collapsed) {
    var content = findContent(el);
    if (content && content !== el) {
      content.style.display = collapsed ? 'none' : '';
      return;
    }
    if (el.tagName !== 'TABLE') return;
    var rows = getDirectRows(el);
    var keep = btn && btn.closest ? btn.closest('tr') : null;
    if (keep && !el.contains(keep)) keep = null; // toggle in <caption> → closest tr is an outer table's
    if (!keep && !el.querySelector(':scope > caption')) keep = rows[0] || null;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] === keep) continue;
      rows[i].style.display = collapsed ? 'none' : '';
    }
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
      applyCollapsedState(el, btn, nowCollapsed);
    }
    // INT-4: expose so mw-customtoggle-* banners can drive this collapsible
    // while keeping the [展开]/[折叠] label in sync.
    el.__mwCollapsibleToggle = toggle;
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
      // INT-4: content-less collapsible div — wrap everything after the
      // toggle into a real .mw-collapsible-content so collapse/expand and
      // the mw-collapsed initial state have something to hide.
      if (!el.querySelector('.mw-collapsible-content')) {
        var wrap = document.createElement('div');
        wrap.className = 'mw-collapsible-content';
        var node = btn.nextSibling, next;
        while (node) { next = node.nextSibling; wrap.appendChild(node); node = next; }
        el.appendChild(wrap);
      }
    }

    // Apply initial collapsed state (INT-1: row-level for tables, so the
    // title row + toggle stay visible)
    if (isCollapsed) applyCollapsedState(el, btn, true);
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

    // INT-4: delegated mw-customtoggle-<id> handler (was entirely missing).
    // Clicking an element whose class contains mw-customtoggle-<id> toggles
    // every collapsible with id="mw-customcollapsible-<id>". querySelectorAll
    // on [id=...] tolerates the duplicate ids some pages emit (one id may map
    // to multiple collapsibles). Clicks landing inside an <a> pass through to
    // navigation; the injected [展开]/[折叠] anchor stops propagation itself.
    document.addEventListener('click', function (e) {
      var toggler = null;
      for (var n = e.target; n && n.nodeType === 1; n = n.parentElement) {
        if (n.tagName === 'A') return; // let links navigate
        if (typeof n.className === 'string' && n.className.indexOf('mw-customtoggle-') !== -1) {
          toggler = n;
          break;
        }
      }
      if (!toggler) return;
      var cl = toggler.classList;
      for (var c = 0; c < cl.length; c++) {
        var m = /^mw-customtoggle-(.+)$/.exec(cl[c]);
        if (!m) continue;
        var sel = '[id="mw-customcollapsible-' +
          m[1].replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"]';
        var targets;
        try { targets = document.querySelectorAll(sel); } catch (err) { continue; }
        for (var t = 0; t < targets.length; t++) {
          var target = targets[t];
          if (typeof target.__mwCollapsibleToggle === 'function') {
            target.__mwCollapsibleToggle(); // reuse toggle: state + label in sync
          } else {
            // Collapsible that never got our toggle (pre-existing toggle
            // markup): flip state directly.
            var nowCollapsed = target.classList.toggle('mw-collapsed');
            applyCollapsedState(target, null, nowCollapsed);
          }
        }
      }
    });
  }

  // Move the page TOC into .layout as a real third flex column (sticky right
   // rail) on wide viewports. This reserves physical space so article text can
   // never overlap it (float+sticky did overlap). Narrow screens leave it
   // inline as a full-width block.
  function setupRightToc() {
    var toc = document.querySelector('.page-toc-v2');
    var layout = document.querySelector('.layout');
    if (!toc || !layout) return;
    if (window.innerWidth <= 900) return;       // narrow: keep inline block
    if (toc.parentElement === layout) return;    // already a flex column
    layout.appendChild(toc);
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
    document.addEventListener('DOMContentLoaded', function () { init(); setupRightToc(); });
  } else {
    init();
    setupRightToc();
  }
})();
