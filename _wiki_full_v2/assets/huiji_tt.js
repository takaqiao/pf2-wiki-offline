/* huiji_tt.js — rich-text hover tooltip for offline wiki.
 *
 * Pages parsed from pf2.huijiwiki.com contain
 *   <span class="huiji-tt" data-template="X" data-params="Y,Z" data-sep=",">
 *     <a href="../pages/<target>.html" title="...">label</a>
 *   </span>
 * On the live site, JS expands this into a rich popover. Offline we
 * mimic that: hover -> fetch the target page, extract a short
 * statblock/summary, show it in a floating .pf2-tt-popup card.
 *
 * Highlights:
 *   - Vanilla JS, no deps
 *   - One shared popup element (reused, repositioned per hover)
 *   - Async fetch + per-URL cache (sessionStorage + in-memory)
 *   - 200 ms grace period when leaving (lets user move into popup)
 *   - Dark-mode picks up via CSS variables in _v2_compat.css
 *   - Smart placement: prefers below, flips above if no room
 *   - Disabled on touch / fine:none (we lose hover semantics)
 *
 * Loaded via <script defer src="../assets/huiji_tt.js?v=v3a">.
 */
(function () {
  'use strict';

  // --- config --------------------------------------------------------------
  var CLOSE_DELAY_MS = 200;
  var OPEN_DELAY_MS = 120; // tiny delay so passing-through hover doesn't fire
  var MAX_TEXT_CHARS = 220;
  var FETCH_TIMEOUT_MS = 4000;
  var CACHE_PREFIX = 'pf2tt:';

  // --- state ---------------------------------------------------------------
  var popupEl = null;
  var popupArrow = null;
  var currentAnchor = null;
  var closeTimer = null;
  var openTimer = null;
  var hoverInsidePopup = false;
  var memCache = Object.create(null);
  var inflight = Object.create(null);

  // --- utils ---------------------------------------------------------------
  function isTouchOnly() {
    try {
      return window.matchMedia('(hover: none)').matches;
    } catch (e) { return false; }
  }

  function clearTimer(t) { if (t) clearTimeout(t); return null; }

  function ensurePopup() {
    if (popupEl) return popupEl;
    popupEl = document.createElement('div');
    popupEl.className = 'pf2-tt-popup';
    popupEl.setAttribute('role', 'tooltip');
    popupEl.setAttribute('aria-hidden', 'true');
    popupEl.style.display = 'none';
    // child slots so we can update without re-allocating
    var arrow = document.createElement('div');
    arrow.className = 'pf2-tt-arrow';
    var body = document.createElement('div');
    body.className = 'pf2-tt-body';
    popupEl.appendChild(arrow);
    popupEl.appendChild(body);
    popupArrow = arrow;
    // pointer events on popup itself: let user move cursor in to scroll/click
    popupEl.addEventListener('mouseenter', function () {
      hoverInsidePopup = true;
      closeTimer = clearTimer(closeTimer);
    });
    popupEl.addEventListener('mouseleave', function () {
      hoverInsidePopup = false;
      scheduleClose();
    });
    document.body.appendChild(popupEl);
    return popupEl;
  }

  function setPopupContent(html, opts) {
    var p = ensurePopup();
    var body = p.querySelector('.pf2-tt-body');
    body.innerHTML = html;
    if (opts && opts.loading) {
      p.classList.add('is-loading');
    } else {
      p.classList.remove('is-loading');
    }
    if (opts && opts.error) {
      p.classList.add('is-error');
    } else {
      p.classList.remove('is-error');
    }
  }

  function showPopup() {
    var p = ensurePopup();
    p.style.display = 'block';
    p.setAttribute('aria-hidden', 'false');
  }

  function hidePopup() {
    if (!popupEl) return;
    popupEl.style.display = 'none';
    popupEl.setAttribute('aria-hidden', 'true');
    currentAnchor = null;
  }

  function positionPopup(anchor) {
    var p = ensurePopup();
    // Reset placement to measure natural size at left/top 0
    p.style.left = '0px';
    p.style.top = '0px';
    p.style.maxWidth = '360px';
    var rect = anchor.getBoundingClientRect();
    var pw = p.offsetWidth;
    var ph = p.offsetHeight;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var scrollX = window.scrollX || window.pageXOffset;
    var scrollY = window.scrollY || window.pageYOffset;

    var margin = 8;
    // Prefer below, flip above if no room
    var top = rect.bottom + scrollY + margin;
    var placeAbove = false;
    if (rect.bottom + ph + margin > vh - 4 && rect.top > ph + margin) {
      top = rect.top + scrollY - ph - margin;
      placeAbove = true;
    }
    // Horizontal: align left edge with anchor, but clamp into viewport
    var left = rect.left + scrollX;
    if (left + pw > scrollX + vw - 4) {
      left = scrollX + vw - pw - 4;
    }
    if (left < scrollX + 4) left = scrollX + 4;

    p.style.left = left + 'px';
    p.style.top = top + 'px';
    p.classList.toggle('pf2-tt-above', placeAbove);
    p.classList.toggle('pf2-tt-below', !placeAbove);

    // Arrow horizontal position: try to point at anchor center
    if (popupArrow) {
      var anchorCenter = rect.left + scrollX + rect.width / 2;
      var arrowX = anchorCenter - left;
      arrowX = Math.max(12, Math.min(pw - 12, arrowX));
      popupArrow.style.left = arrowX + 'px';
    }
  }

  // --- content extraction --------------------------------------------------
  function summarizeDoc(doc, targetUrl) {
    var content = doc.getElementById('mw-content-text');
    if (!content) return null;
    // Prefer the .quote-block.statblock (spell/feat/item stat card)
    var statblock = content.querySelector('.quote-block.statblock, .statblock');
    var title = doc.querySelector('title');
    var titleTxt = title ? title.textContent.replace(/\s*-\s*PF2.*$/, '').trim() : '';
    var headerHtml = '';
    if (titleTxt) {
      headerHtml = '<div class="pf2-tt-title"><a href="' +
        escapeAttr(targetUrl) + '">' + escapeText(titleTxt) + '</a></div>';
    }

    if (statblock) {
      // Clone and trim images / heavy blocks
      var clone = statblock.cloneNode(true);
      clone.querySelectorAll('img').forEach(function (n) { n.remove(); });
      // Strip inline floats
      clone.querySelectorAll('[style]').forEach(function (n) {
        n.removeAttribute('style');
      });
      // Remove "click to edit data" links and similar trailing controls
      clone.querySelectorAll('a[href*="Data:"]').forEach(function (a) {
        var row = a.closest('div');
        if (row) row.remove();
      });
      return headerHtml + '<div class="pf2-tt-card">' + clone.innerHTML + '</div>';
    }

    // Fallback: first paragraph(s) of mw-parser-output, ~200 chars
    var parser = content.querySelector('.mw-parser-output') || content;
    var paras = parser.querySelectorAll('p');
    var buf = '';
    for (var i = 0; i < paras.length && buf.length < MAX_TEXT_CHARS; i++) {
      var t = paras[i].textContent.replace(/\s+/g, ' ').trim();
      if (!t) continue;
      buf += (buf ? ' ' : '') + t;
    }
    if (buf.length > MAX_TEXT_CHARS) buf = buf.slice(0, MAX_TEXT_CHARS) + '…';
    if (!buf) {
      // Last resort: text of the content area
      buf = (parser.textContent || '').replace(/\s+/g, ' ').trim().slice(0, MAX_TEXT_CHARS);
      if (buf.length === MAX_TEXT_CHARS) buf += '…';
    }
    if (!buf) return headerHtml + '<div class="pf2-tt-empty">无内容预览</div>';
    return headerHtml + '<div class="pf2-tt-text">' + escapeText(buf) + '</div>';
  }

  function escapeText(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  function escapeAttr(s) {
    return escapeText(s).replace(/"/g, '&quot;');
  }

  function fromCache(url) {
    if (memCache[url]) return memCache[url];
    try {
      var raw = sessionStorage.getItem(CACHE_PREFIX + url);
      if (raw) { memCache[url] = raw; return raw; }
    } catch (e) { /* sessionStorage may throw in some sandboxes */ }
    return null;
  }
  function toCache(url, html) {
    memCache[url] = html;
    try { sessionStorage.setItem(CACHE_PREFIX + url, html); } catch (e) { /* quota */ }
  }

  function fetchAndSummarize(url) {
    if (inflight[url]) return inflight[url];
    var cached = fromCache(url);
    if (cached) return Promise.resolve(cached);

    var ctrl = ('AbortController' in window) ? new AbortController() : null;
    var to = setTimeout(function () { if (ctrl) ctrl.abort(); }, FETCH_TIMEOUT_MS);

    var p = fetch(url, { credentials: 'same-origin', signal: ctrl ? ctrl.signal : undefined })
      .then(function (resp) {
        clearTimeout(to);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.text();
      })
      .then(function (text) {
        var doc = new DOMParser().parseFromString(text, 'text/html');
        var html = summarizeDoc(doc, url) || '<div class="pf2-tt-empty">无内容预览</div>';
        toCache(url, html);
        delete inflight[url];
        return html;
      })
      .catch(function (err) {
        clearTimeout(to);
        delete inflight[url];
        throw err;
      });
    inflight[url] = p;
    return p;
  }

  // --- event handlers ------------------------------------------------------
  function getTargetUrl(span) {
    var a = span.querySelector('a[href]');
    if (!a) return null;
    var href = a.getAttribute('href');
    if (!href) return null;
    // ignore external links
    if (/^(?:[a-z]+:)?\/\//i.test(href)) return null;
    if (href.indexOf('#') === 0) return null;
    // resolve relative URL using <base> or current document
    try {
      return new URL(href, document.baseURI).toString();
    } catch (e) {
      return href;
    }
  }

  function previewLabelHtml(span) {
    // Synchronous fallback while we fetch
    var tmpl = span.getAttribute('data-template') || '';
    var params = span.getAttribute('data-params') || '';
    var sep = span.getAttribute('data-sep') || ',';
    var parts = params ? params.split(sep).filter(Boolean) : [];
    var label = span.textContent.replace(/\s+/g, ' ').trim();
    var tagBits = parts.length ? parts.join(' · ') : '';
    var html = '';
    if (label) html += '<div class="pf2-tt-title">' + escapeText(label) + '</div>';
    if (tagBits) html += '<div class="pf2-tt-tags">' + escapeText(tagBits) + '</div>';
    if (tmpl) html += '<div class="pf2-tt-tmpl">[' + escapeText(tmpl) + ']</div>';
    return html || '<div class="pf2-tt-empty">载入中…</div>';
  }

  function scheduleClose() {
    closeTimer = clearTimer(closeTimer);
    closeTimer = setTimeout(function () {
      if (hoverInsidePopup) return;
      hidePopup();
    }, CLOSE_DELAY_MS);
  }

  function onEnter(e) {
    var span = e.currentTarget;
    closeTimer = clearTimer(closeTimer);
    openTimer = clearTimer(openTimer);
    openTimer = setTimeout(function () { openFor(span); }, OPEN_DELAY_MS);
  }

  function onLeave() {
    openTimer = clearTimer(openTimer);
    scheduleClose();
  }

  function openFor(span) {
    if (currentAnchor === span && popupEl && popupEl.style.display === 'block') {
      return; // already shown
    }
    currentAnchor = span;
    var url = getTargetUrl(span);
    // Show synchronous fallback immediately
    var initial = '<div class="pf2-tt-loading">' + previewLabelHtml(span) + '</div>';
    setPopupContent(initial, { loading: true });
    showPopup();
    positionPopup(span);

    if (!url) {
      setPopupContent(previewLabelHtml(span), {});
      positionPopup(span);
      return;
    }

    fetchAndSummarize(url).then(function (html) {
      // make sure we're still pointing at the same anchor
      if (currentAnchor !== span) return;
      setPopupContent(html, {});
      positionPopup(span);
    }).catch(function () {
      if (currentAnchor !== span) return;
      setPopupContent(previewLabelHtml(span) +
        '<div class="pf2-tt-err">无法加载预览</div>', { error: true });
      positionPopup(span);
    });
  }

  function init() {
    if (isTouchOnly()) {
      // Touch-only: keep legacy behavior (title attr fallback)
      document.querySelectorAll('span.huiji-tt').forEach(function (el) {
        if (el.getAttribute('title')) return;
        var tmpl = el.getAttribute('data-template') || '';
        var params = el.getAttribute('data-params') || '';
        var sep = el.getAttribute('data-sep') || ',';
        var parts = params ? params.split(sep).filter(Boolean) : [];
        var tip = parts.join(' · ');
        if (tmpl) tip = tip ? tip + '   [' + tmpl + ']' : tmpl;
        if (tip) el.setAttribute('title', tip);
        el.classList.add('huiji-tt-rendered');
      });
      return;
    }

    var els = document.querySelectorAll('span.huiji-tt');
    els.forEach(function (el) {
      el.classList.add('huiji-tt-rendered');
      // Strip prior plain title attributes so they don't double-render
      // alongside our rich popup.
      el.removeAttribute('title');
      el.addEventListener('mouseenter', onEnter);
      el.addEventListener('mouseleave', onLeave);
      // Keyboard a11y: focus/blur trigger same flow
      el.addEventListener('focusin', onEnter);
      el.addEventListener('focusout', onLeave);
    });

    // Global ESC hides popup
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && popupEl && popupEl.style.display === 'block') {
        hidePopup();
      }
    });
    // Hide on scroll/resize (would otherwise mis-position)
    window.addEventListener('scroll', function () {
      if (currentAnchor) hidePopup();
    }, { passive: true });
    window.addEventListener('resize', function () {
      if (currentAnchor) hidePopup();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
