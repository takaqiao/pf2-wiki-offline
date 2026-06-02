/* image_lightbox.js — click an image inside .mw-parser-output to open it in
 * a fullscreen overlay (lightbox). Mirrors the huijiwiki online behaviour.
 *
 * Loaded via <script defer src="../assets/image_lightbox.js"> on every
 * built HTML page (build_v2.py).
 *
 * Vanilla JS, no dependencies. Idempotent (safe to load twice).
 */
(function () {
  'use strict';

  if (window.__pf2LightboxLoaded) return;
  window.__pf2LightboxLoaded = true;

  var OVERLAY_ID = 'pf2-lightbox-overlay';

  function isLightboxableImg(img) {
    if (!img || img.tagName !== 'IMG') return false;
    // Only images inside content body.
    if (!img.closest || !img.closest('.mw-parser-output')) return false;
    // Skip tiny UI icons (action glyphs, gold-box icons, etc.).
    // Use displayed size (rendered/declared) — NOT naturalWidth, which
    // reflects the source-file resolution and can be much larger.
    var rect = img.getBoundingClientRect();
    var dispW = rect.width || img.clientWidth ||
                parseInt(img.getAttribute('width') || '0', 10);
    var dispH = rect.height || img.clientHeight ||
                parseInt(img.getAttribute('height') || '0', 10);
    if (dispW && dispH && dispW < 60 && dispH < 60) return false;
    // Skip images explicitly opted out.
    if (img.hasAttribute('data-no-lightbox')) return false;
    return true;
  }

  function pickSrc(img) {
    // Prefer the local rendered src (offline-safe). Ignore data-original-src
    // (remote huiji-thumb URL) because Tauri/offline cannot fetch it.
    return img.currentSrc || img.src || img.getAttribute('src') || '';
  }

  function pickAlt(img) {
    return img.getAttribute('alt') || img.getAttribute('title') || '';
  }

  function close() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
    document.removeEventListener('keydown', onKey, true);
    if (document.body) document.body.style.overflow = '';
  }

  function onKey(e) {
    if (e.key === 'Escape' || e.keyCode === 27) {
      e.preventDefault();
      close();
    }
  }

  function open(img) {
    close(); // ensure only one overlay
    var src = pickSrc(img);
    if (!src) return;

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.className = 'pf2-lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', '图片放大预览');

    var big = document.createElement('img');
    big.className = 'pf2-lightbox-img';
    big.src = src;
    big.alt = pickAlt(img);

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'pf2-lightbox-close';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.textContent = '×';
    closeBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      close();
    });

    overlay.appendChild(big);
    overlay.appendChild(closeBtn);

    // Caption from alt/title, shown under the image.
    var capText = pickAlt(img);
    if (capText) {
      var cap = document.createElement('div');
      cap.className = 'pf2-lightbox-cap';
      cap.textContent = capText;
      overlay.appendChild(cap);
    }
    // Clicking the image (or caption) must NOT dismiss — only the backdrop/×.
    big.addEventListener('click', function (e) { e.stopPropagation(); });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) { e.preventDefault(); close(); }
    });

    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey, true);
  }

  function onClick(e) {
    if (e.defaultPrevented) return;
    var t = e.target;
    if (!t) return;
    // Only handle clicks that land on an <img>.
    if (t.tagName !== 'IMG') return;
    if (!isLightboxableImg(t)) return;
    // Suppress wrapping <a> navigation (e.g. <a href="..."><img></a>).
    e.preventDefault();
    e.stopPropagation();
    open(t);
  }

  function attach() {
    document.addEventListener('click', onClick, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attach, { once: true });
  } else {
    attach();
  }
})();
