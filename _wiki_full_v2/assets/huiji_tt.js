/* huiji_tt.js — minimal tooltip activator for offline use.
 *
 * Pages parsed from pf2.huijiwiki.com contain <span class="huiji-tt"
 *   data-template="X" data-params="Y,Z" data-sep=",">…</span>
 *
 * The original site has JS that expands data-template into a popover.
 * Offline we don't run server templates, so we:
 *   1. Walk all .huiji-tt elements
 *   2. Use data-params (split by data-sep) to fill a `title` attribute
 *   3. Add a subtle dotted-underline visual hint
 *
 * Loaded via <script defer src="assets/huiji_tt.js?v=v2b">.
 */
(function() {
  function init() {
    const els = document.querySelectorAll('span.huiji-tt');
    let n = 0;
    for (const el of els) {
      const tmpl = el.getAttribute('data-template') || '';
      const params = el.getAttribute('data-params') || '';
      const sep = el.getAttribute('data-sep') || ',';
      const parts = params ? params.split(sep) : [];
      // Build a readable tooltip
      let tip = '';
      if (parts.length > 0) {
        tip = parts.filter(Boolean).join(' · ');
      }
      if (tmpl) {
        tip = tip ? `${tip}   [${tmpl}]` : tmpl;
      }
      if (tip && !el.getAttribute('title')) {
        el.setAttribute('title', tip);
      }
      // Visual hint
      el.classList.add('huiji-tt-rendered');
      n++;
    }
    if (window.console && n > 0) {
      // No-op, just gives debug visibility
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
