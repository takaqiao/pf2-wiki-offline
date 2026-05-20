/* ============================================================
   wikitable_paginate.js — large-table pagination + search

   Activates on any <table class="wikitable"> (or table whose
   className contains "wikitable") whose tbody row count >= 100.

   Behaviour:
     - Renders a control bar immediately above each large table:
         [search box]   [page-size selector]   [counter]
         [← prev]  1 2 3 … N  [next →]   跳转到: [input] [Go]
     - First page is shown by default (page size 50).
     - Search performs case-insensitive substring match on row
       textContent, debounced. Empty query clears the search filter.
     - Plays nicely with row-visibility set by other scripts
       (filter.js, the inline $CustomFilter widget on 法术列表):
         - external hides (any style="display:none" set elsewhere)
           are treated as filtered-out rows; pagination operates on
           the remaining "candidate" rows.
         - pagination's own hides use the marker class
           "wp-paginated-out". Rows with that class get display:none.
         - We re-evaluate when external scripts mutate tbody.

   Vanilla ES2018. No deps.
   ============================================================ */
(function () {
  'use strict';

  var ROW_THRESHOLD = 100;       // engage at >= 100 rows
  var DEFAULT_PAGE_SIZE = 50;
  var PAGE_SIZE_CHOICES = [25, 50, 100, 200];
  var WINDOW = 2;                // pages on each side of current in pager
  var SEARCH_DEBOUNCE_MS = 150;

  var MARKER = 'wp-paginated-out';

  function ready(fn) {
    if (document.readyState !== 'loading') {
      // Defer one tick so other DOMContentLoaded handlers (filter.js,
      // $CustomFilter on window.load) get to wire up first.
      setTimeout(fn, 0);
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        setTimeout(fn, 0);
      });
    }
  }

  function dataRows(table) {
    var tbody = table.tBodies && table.tBodies[0];
    if (!tbody) return [];
    var rows = tbody.rows;
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (!r.cells || !r.cells.length) continue;
      // Skip rows that are pure header (only <th>, no <td>)
      var hasTd = false;
      for (var j = 0; j < r.cells.length; j++) {
        if (r.cells[j].tagName && r.cells[j].tagName.toLowerCase() === 'td') {
          hasTd = true;
          break;
        }
      }
      if (!hasTd) continue;
      out.push(r);
    }
    return out;
  }

  function externallyHidden(row) {
    // Row is hidden by *something else* if it has display:none and that
    // didn't come from our marker class.
    if (row.classList.contains(MARKER)) return false;
    if (row.style && row.style.display === 'none') return true;
    return false;
  }

  function matchesSearch(row, needle) {
    if (!needle) return true;
    var hay = row.__wpSearchText;
    if (hay === undefined) {
      hay = (row.textContent || '').toLowerCase();
      row.__wpSearchText = hay;
    }
    return hay.indexOf(needle) !== -1;
  }

  function makeEl(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function debounce(fn, wait) {
    var t = null;
    return function () {
      var ctx = this, args = arguments;
      if (t) clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function build(table) {
    var rows = dataRows(table);
    if (rows.length < ROW_THRESHOLD) return null;

    var state = {
      table: table,
      rows: rows,
      candidates: rows.slice(),  // rows passing both search + external filters
      search: '',
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
      mutating: false            // re-entrancy guard
    };

    var ctrl = makeEl('div', 'wikitable-paginate-ctrl');
    ctrl.setAttribute('role', 'toolbar');
    ctrl.setAttribute('aria-label', '表格分页与搜索');

    // --- row 1: search + page size + counter ---
    var row1 = makeEl('div', 'wp-row wp-row-top');

    var searchWrap = makeEl('label', 'wp-search');
    searchWrap.appendChild(makeEl('span', 'wp-search-lbl', '搜索：'));
    var search = makeEl('input', 'wp-search-input');
    search.type = 'search';
    search.placeholder = '输入关键字过滤行';
    search.autocomplete = 'off';
    searchWrap.appendChild(search);
    row1.appendChild(searchWrap);

    var sizeWrap = makeEl('label', 'wp-size');
    sizeWrap.appendChild(makeEl('span', 'wp-size-lbl', '每页：'));
    var sizeSel = makeEl('select', 'wp-size-select');
    for (var i = 0; i < PAGE_SIZE_CHOICES.length; i++) {
      var opt = makeEl('option', null, String(PAGE_SIZE_CHOICES[i]));
      opt.value = String(PAGE_SIZE_CHOICES[i]);
      if (PAGE_SIZE_CHOICES[i] === DEFAULT_PAGE_SIZE) opt.selected = true;
      sizeSel.appendChild(opt);
    }
    sizeWrap.appendChild(sizeSel);
    row1.appendChild(sizeWrap);

    var counter = makeEl('span', 'wp-counter');
    row1.appendChild(counter);

    ctrl.appendChild(row1);

    // --- row 2: pager ---
    var row2 = makeEl('div', 'wp-row wp-row-pager');

    var prev = makeEl('button', 'wp-pager-btn wp-prev', '←');
    prev.type = 'button';
    prev.title = '上一页';
    row2.appendChild(prev);

    var pageList = makeEl('span', 'wp-pages');
    row2.appendChild(pageList);

    var next = makeEl('button', 'wp-pager-btn wp-next', '→');
    next.type = 'button';
    next.title = '下一页';
    row2.appendChild(next);

    var jumpWrap = makeEl('span', 'wp-jump');
    jumpWrap.appendChild(makeEl('span', 'wp-jump-lbl', '跳转到：'));
    var jumpInput = makeEl('input', 'wp-jump-input');
    jumpInput.type = 'number';
    jumpInput.min = '1';
    jumpInput.step = '1';
    jumpInput.inputMode = 'numeric';
    jumpWrap.appendChild(jumpInput);
    var jumpBtn = makeEl('button', 'wp-jump-btn', 'Go');
    jumpBtn.type = 'button';
    jumpWrap.appendChild(jumpBtn);
    row2.appendChild(jumpWrap);

    ctrl.appendChild(row2);

    // Insert ctrl just before the table
    table.parentNode.insertBefore(ctrl, table);

    // ---------- core logic ----------
    function refreshRowList() {
      // Re-collect rows in current DOM order so sort/reorder by other
      // scripts (e.g. wikitable_sort.js) is reflected in pagination.
      state.rows = dataRows(state.table);
    }

    function rebuildCandidates() {
      refreshRowList();
      var needle = state.search;
      var out = [];
      for (var i = 0; i < state.rows.length; i++) {
        var r = state.rows[i];
        if (externallyHidden(r)) continue;
        if (!matchesSearch(r, needle)) continue;
        out.push(r);
      }
      state.candidates = out;
    }

    function pageCount() {
      if (state.candidates.length === 0) return 1;
      return Math.max(1, Math.ceil(state.candidates.length / state.pageSize));
    }

    function clampPage() {
      var pc = pageCount();
      if (state.page < 1) state.page = 1;
      if (state.page > pc) state.page = pc;
    }

    function applyPaging() {
      state.mutating = true;
      var pc = pageCount();
      clampPage();
      var lo = (state.page - 1) * state.pageSize;
      var hi = lo + state.pageSize;

      // First, mark all rows: candidates get index, non-candidates get
      // pagination-hide cleared (they're hidden by external filter or
      // entirely visible already).
      var candSet = state.candidates;
      var candFlags = Object.create(null);
      for (var i = 0; i < candSet.length; i++) {
        candFlags[i] = (i >= lo && i < hi);
      }

      // Pass over all rows once.
      var idx = 0;
      for (var k = 0; k < state.rows.length; k++) {
        var r = state.rows[k];
        var hadMarker = r.classList.contains(MARKER);
        var isCand = (!externallyHidden(r)) && matchesSearch(r, state.search);
        if (isCand) {
          var inPage = candFlags[idx];
          idx++;
          if (inPage) {
            if (hadMarker) {
              r.classList.remove(MARKER);
              if (r.style.display === 'none') r.style.display = '';
            }
          } else {
            if (!hadMarker) {
              r.classList.add(MARKER);
              r.style.display = 'none';
            }
          }
        } else {
          // Not a candidate — either externally hidden or search-miss.
          // We should not show this row on the page even if it doesn't
          // currently carry display:none (e.g. search miss but not
          // filtered by something else).
          var extHide = externallyHidden(r);
          if (!extHide && state.search) {
            // hidden by our search
            if (!hadMarker) {
              r.classList.add(MARKER);
              r.style.display = 'none';
            }
          } else if (hadMarker && extHide) {
            // external filter took over — drop our marker, leave display alone
            r.classList.remove(MARKER);
          }
        }
      }

      renderPager(pc);
      renderCounter();
      state.mutating = false;
    }

    function renderCounter() {
      var total = state.rows.length;
      var matched = state.candidates.length;
      var pc = pageCount();
      var lo = (state.page - 1) * state.pageSize + 1;
      var hi = Math.min(state.page * state.pageSize, matched);
      if (matched === 0) {
        counter.textContent = '0 / ' + total + ' 行（无匹配）';
      } else if (matched === total) {
        counter.textContent = '第 ' + state.page + ' / ' + pc + ' 页 · 显示 ' +
          lo + '–' + hi + ' / ' + total + ' 行';
      } else {
        counter.textContent = '第 ' + state.page + ' / ' + pc + ' 页 · 显示 ' +
          lo + '–' + hi + ' / ' + matched + ' 行（共 ' + total + '）';
      }
    }

    function renderPager(pc) {
      pageList.innerHTML = '';
      var p = state.page;
      // Build list of page numbers with ellipses
      var nums = [];
      var lo = Math.max(2, p - WINDOW);
      var hi = Math.min(pc - 1, p + WINDOW);
      nums.push(1);
      if (lo > 2) nums.push('…');
      for (var n = lo; n <= hi; n++) nums.push(n);
      if (hi < pc - 1) nums.push('…');
      if (pc > 1) nums.push(pc);

      for (var i = 0; i < nums.length; i++) {
        var v = nums[i];
        if (v === '…') {
          var e = makeEl('span', 'wp-ellipsis', '…');
          pageList.appendChild(e);
        } else {
          var b = makeEl('button', 'wp-page-btn' + (v === p ? ' wp-current' : ''), String(v));
          b.type = 'button';
          b.setAttribute('data-page', String(v));
          if (v === p) b.setAttribute('aria-current', 'page');
          pageList.appendChild(b);
        }
      }
      prev.disabled = (p <= 1);
      next.disabled = (p >= pc);
      jumpInput.max = String(pc);
      jumpInput.placeholder = '1–' + pc;
    }

    function recompute(resetPage) {
      rebuildCandidates();
      if (resetPage) state.page = 1;
      applyPaging();
    }

    // ---------- event wiring ----------
    var debouncedSearch = debounce(function () {
      state.search = (search.value || '').trim().toLowerCase();
      recompute(true);
    }, SEARCH_DEBOUNCE_MS);
    search.addEventListener('input', debouncedSearch);

    sizeSel.addEventListener('change', function () {
      var v = parseInt(sizeSel.value, 10);
      if (!isNaN(v) && v > 0) {
        state.pageSize = v;
        // Try to keep approximately the same anchor row: recompute on page 1.
        recompute(true);
      }
    });

    prev.addEventListener('click', function () {
      if (state.page > 1) { state.page--; applyPaging(); scrollIntoView(); }
    });
    next.addEventListener('click', function () {
      if (state.page < pageCount()) { state.page++; applyPaging(); scrollIntoView(); }
    });

    pageList.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.classList || !t.classList.contains('wp-page-btn')) return;
      var n = parseInt(t.getAttribute('data-page'), 10);
      if (!isNaN(n)) {
        state.page = n;
        applyPaging();
        scrollIntoView();
      }
    });

    function doJump() {
      var n = parseInt(jumpInput.value, 10);
      if (isNaN(n)) return;
      state.page = n;
      applyPaging();
      scrollIntoView();
    }
    jumpBtn.addEventListener('click', doJump);
    jumpInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doJump(); }
    });

    function scrollIntoView() {
      // Keep the control bar visible: only scroll if ctrl is above viewport
      var rect = ctrl.getBoundingClientRect();
      if (rect.top < 0) ctrl.scrollIntoView({ block: 'start', behavior: 'instant' in window ? 'instant' : 'auto' });
    }

    // Observe tbody so external filters + sort scripts trigger a
    // pagination refresh automatically.
    var tbody = table.tBodies[0];
    if (tbody && 'MutationObserver' in window) {
      var pending = false;
      var schedule = function () {
        if (pending || state.mutating) return;
        pending = true;
        // requestAnimationFrame coalesces a burst of changes from
        // batched filter/sort operations into one re-paint.
        var raf = window.requestAnimationFrame || function (cb) { return setTimeout(cb, 0); };
        raf(function () {
          pending = false;
          recompute(false);
        });
      };
      var mo = new MutationObserver(function (muts) {
        if (state.mutating) return;
        for (var i = 0; i < muts.length; i++) {
          var m = muts[i];
          if (m.type === 'childList') { schedule(); return; }
          if (m.type === 'attributes' &&
              (m.attributeName === 'style' || m.attributeName === 'class')) {
            schedule(); return;
          }
        }
      });
      mo.observe(tbody, {
        attributes: true,
        attributeFilter: ['style', 'class'],
        subtree: true,
        childList: true
      });
    }

    // Initial paint
    recompute(true);
    return state;
  }

  function init() {
    var tables = document.querySelectorAll('table');
    for (var i = 0; i < tables.length; i++) {
      var t = tables[i];
      var cls = t.className || '';
      if (cls.indexOf('wikitable') === -1) continue;
      if (t.__wpPagerInit) continue;
      // Skip tables driven by the wiki's CustomFilter ($CustomFilter), which
      // owns row visibility via .cf-item display toggling. Two row-visibility
      // systems fight: CustomFilter's window.load pass forces display='' on all
      // matching rows, overriding our pagination's display:none — leaving all
      // 816 rows visible and the pager frozen. CustomFilter already provides
      // filtering, so pagination is redundant here.
      if (cls.indexOf('filterable') !== -1 || cls.indexOf('cf-container') !== -1
          || t.querySelector('.cf-item')) {
        continue;
      }
      try {
        var s = build(t);
        if (s) t.__wpPagerInit = true;
      } catch (e) {
        // Swallow per-table errors; never block the page.
        if (window.console && console.warn) console.warn('wikitable_paginate: failed on table', e);
      }
    }
  }

  // Expose for manual re-init if needed
  window.wikitablePaginateInit = init;

  ready(init);
})();
