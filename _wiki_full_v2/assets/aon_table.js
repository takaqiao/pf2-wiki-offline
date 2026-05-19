/* aon_table.js — Phase 6 / Agent TABLE
 *
 * Click a sortable <th> to sort the table by that column.
 * - Reads td[data-sort-value] when present (preferred for numeric sort);
 *   otherwise sorts by textContent.
 * - Toggles asc/desc/none on repeated clicks (3-state cycle: asc -> desc -> reset).
 * - Highlights the active sort column via .sort-asc / .sort-desc on the th.
 * - Vanilla JS, no deps. Works for every <table class="aon-table sortable">.
 * - Each cell can opt-in to numeric sort via class="num" on the th, or
 *   data-sort-value containing a parseable number.
 * - Sort is stable (Array.prototype.sort in modern browsers is stable as of ES2019).
 *
 * Also updates the optional .aon-row-count badge with the current visible row count.
 */
(function () {
  'use strict';

  function isNumeric(v) {
    if (v === null || v === undefined || v === '') return false;
    var n = Number(v);
    return !Number.isNaN(n) && Number.isFinite(n);
  }

  function cellSortValue(cell, isNumCol) {
    if (!cell) return isNumCol ? Number.POSITIVE_INFINITY : '';
    var sv = cell.getAttribute('data-sort-value');
    if (sv !== null) {
      if (isNumCol) {
        var n = Number(sv);
        return Number.isFinite(n) ? n : Number.POSITIVE_INFINITY;
      }
      return sv;
    }
    var txt = (cell.textContent || '').trim();
    if (isNumCol) {
      var m = txt.match(/-?\d+(?:\.\d+)?/);
      return m ? Number(m[0]) : Number.POSITIVE_INFINITY;
    }
    return txt;
  }

  function compareValues(a, b, isNumCol) {
    if (isNumCol) {
      if (a === b) return 0;
      return a < b ? -1 : 1;
    }
    // Locale-aware compare (handles CJK collation OK)
    return String(a).localeCompare(String(b), 'zh-Hans', { numeric: true });
  }

  function clearSortState(table) {
    table.querySelectorAll('thead th').forEach(function (th) {
      th.classList.remove('sort-asc');
      th.classList.remove('sort-desc');
    });
  }

  function sortTable(table, thIndex, direction) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.rows);
    var headRow = table.tHead && table.tHead.rows[0];
    var th = headRow && headRow.cells[thIndex];
    var isNumCol = th && (th.classList.contains('num') || /level/i.test(th.getAttribute('data-sort') || ''));

    rows.sort(function (r1, r2) {
      var v1 = cellSortValue(r1.cells[thIndex], isNumCol);
      var v2 = cellSortValue(r2.cells[thIndex], isNumCol);
      var c = compareValues(v1, v2, isNumCol);
      return direction === 'desc' ? -c : c;
    });

    var frag = document.createDocumentFragment();
    rows.forEach(function (r) { frag.appendChild(r); });
    tbody.appendChild(frag);

    clearSortState(table);
    if (th) th.classList.add(direction === 'desc' ? 'sort-desc' : 'sort-asc');
  }

  function resetSort(table) {
    // Restore original order using stored sequence index
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.rows);
    rows.sort(function (r1, r2) {
      var i1 = Number(r1.getAttribute('data-original-index') || 0);
      var i2 = Number(r2.getAttribute('data-original-index') || 0);
      return i1 - i2;
    });
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) { frag.appendChild(r); });
    tbody.appendChild(frag);
    clearSortState(table);
  }

  function updateRowCount(table) {
    var section = table.closest('.aon-table-section');
    if (!section) return;
    var badge = section.querySelector('.aon-row-count');
    if (!badge) return;
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var visible = 0;
    Array.prototype.forEach.call(tbody.rows, function (r) {
      if (!r.classList.contains('aon-row-hidden')) visible++;
    });
    var total = tbody.rows.length;
    badge.textContent = visible === total
      ? '· 共 ' + total + ' 条'
      : '· 显示 ' + visible + ' / ' + total + ' 条';
  }

  function bindTable(table) {
    if (!table.tHead) return;
    var headRow = table.tHead.rows[0];
    if (!headRow) return;

    // Stamp original order on rows for reset
    var tbody = table.tBodies[0];
    if (tbody) {
      Array.prototype.forEach.call(tbody.rows, function (r, i) {
        if (!r.hasAttribute('data-original-index')) {
          r.setAttribute('data-original-index', i);
        }
      });
    }

    Array.prototype.forEach.call(headRow.cells, function (th, idx) {
      if (!th.classList.contains('sortable')) return;
      th.setAttribute('role', 'button');
      th.setAttribute('tabindex', '0');
      var handler = function () {
        var cur = th.classList.contains('sort-asc') ? 'asc'
                : th.classList.contains('sort-desc') ? 'desc'
                : 'none';
        var next = cur === 'none' ? 'asc' : (cur === 'asc' ? 'desc' : 'none');
        if (next === 'none') {
          resetSort(table);
        } else {
          sortTable(table, idx, next);
        }
        updateRowCount(table);
      };
      th.addEventListener('click', handler);
      th.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          handler();
        }
      });
    });

    updateRowCount(table);
  }

  function init() {
    document.querySelectorAll('table.aon-table.sortable').forEach(bindTable);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose a tiny re-init hook for Agent FILT to call after filter changes
  window.aonTableRecount = function () {
    document.querySelectorAll('table.aon-table.sortable').forEach(updateRowCount);
  };
})();
