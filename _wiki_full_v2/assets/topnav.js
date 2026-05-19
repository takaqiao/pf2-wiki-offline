/* ============================================================
   topnav.js — Phase 6, Agent TOPNAV
   Minimal click/hover dropdown controller with:
     - click toggles .open on the parent .topnav-item
     - hover opens, mouseleave closes (after grace)
     - keyboard: Enter/Space toggles; ArrowDown enters panel;
       ArrowUp/ArrowDown navigates within panel; Esc closes
     - click outside collapses any open dropdown
     - search field submits to ../search.html (root) or
       search.html (sub) — script reads data-search-target on
       the form to know where to send the query
   No external dependencies. ~3 KB unminified.
   ============================================================ */
(function () {
  'use strict';

  function topnav_ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  topnav_ready(function () {
    var nav = document.querySelector('.topnav');
    if (!nav) return;

    var items = nav.querySelectorAll('.topnav-item');
    var triggers = nav.querySelectorAll('.topnav-trigger');
    var closeTimers = new Map();

    function closeAll(except) {
      items.forEach(function (it) {
        if (it !== except) {
          it.classList.remove('open');
          var tr = it.querySelector('.topnav-trigger');
          if (tr) tr.setAttribute('aria-expanded', 'false');
        }
      });
    }

    function openItem(it) {
      if (!it) return;
      closeAll(it);
      it.classList.add('open');
      var tr = it.querySelector('.topnav-trigger');
      if (tr) tr.setAttribute('aria-expanded', 'true');
    }

    function toggleItem(it) {
      if (!it) return;
      if (it.classList.contains('open')) {
        it.classList.remove('open');
        var tr = it.querySelector('.topnav-trigger');
        if (tr) tr.setAttribute('aria-expanded', 'false');
      } else {
        openItem(it);
      }
    }

    /* ---- click on trigger ---- */
    triggers.forEach(function (tr) {
      tr.setAttribute('aria-expanded', 'false');
      tr.setAttribute('aria-haspopup', 'true');
      tr.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        toggleItem(tr.closest('.topnav-item'));
      });
    });

    /* ---- hover open with grace-period close ---- */
    items.forEach(function (it) {
      it.addEventListener('mouseenter', function () {
        var t = closeTimers.get(it);
        if (t) { clearTimeout(t); closeTimers.delete(it); }
        openItem(it);
      });
      it.addEventListener('mouseleave', function () {
        var t = setTimeout(function () {
          it.classList.remove('open');
          var tr = it.querySelector('.topnav-trigger');
          if (tr) tr.setAttribute('aria-expanded', 'false');
        }, 180);
        closeTimers.set(it, t);
      });
    });

    /* ---- click outside closes ---- */
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target)) closeAll(null);
    });

    /* ---- keyboard nav ---- */
    nav.addEventListener('keydown', function (e) {
      var tgt = e.target;
      if (!tgt) return;
      var key = e.key;

      // On trigger: Enter/Space toggles, ArrowDown opens + focuses 1st link
      if (tgt.classList && tgt.classList.contains('topnav-trigger')) {
        var item = tgt.closest('.topnav-item');
        if (key === 'Enter' || key === ' ') {
          e.preventDefault();
          toggleItem(item);
        } else if (key === 'ArrowDown') {
          e.preventDefault();
          openItem(item);
          var firstLink = item.querySelector('.topnav-panel a');
          if (firstLink) firstLink.focus();
        } else if (key === 'Escape') {
          closeAll(null);
        } else if (key === 'ArrowRight' || key === 'ArrowLeft') {
          e.preventDefault();
          var sibs = Array.prototype.slice.call(triggers);
          var idx = sibs.indexOf(tgt);
          var next = key === 'ArrowRight'
            ? sibs[(idx + 1) % sibs.length]
            : sibs[(idx - 1 + sibs.length) % sibs.length];
          if (next) next.focus();
        }
        return;
      }

      // Inside a panel link
      if (tgt.classList && tgt.classList.contains('topnav-link')) {
        var panel = tgt.closest('.topnav-panel');
        if (!panel) return;
        var links = Array.prototype.slice.call(panel.querySelectorAll('a.topnav-link'));
        var i = links.indexOf(tgt);
        if (key === 'ArrowDown') {
          e.preventDefault();
          (links[(i + 1) % links.length] || links[0]).focus();
        } else if (key === 'ArrowUp') {
          e.preventDefault();
          (links[(i - 1 + links.length) % links.length] || links[0]).focus();
        } else if (key === 'Escape') {
          e.preventDefault();
          var trig = panel.parentNode.querySelector('.topnav-trigger');
          closeAll(null);
          if (trig) trig.focus();
        } else if (key === 'Tab') {
          // Tab out closes the panel
          closeAll(null);
        }
      }
    });

    /* ---- search submit ---- */
    var form = nav.querySelector('.topnav-search');
    if (form && form.tagName === 'FORM') {
      form.addEventListener('submit', function (e) {
        var input = form.querySelector('.topnav-search-input');
        if (!input || !input.value.trim()) {
          e.preventDefault();
          input && input.focus();
        }
        // otherwise default browser submit handles GET to action=
      });
    }
  });
})();
