/* wikitable_sort.js — click-to-sort headers for table.wikitable.
 *
 * The upstream MediaWiki HTML used to mark sortable tables with
 * `class="sortable"` and provide `jquery.tablesorter`; the huiji
 * action=parse output strips both. This module re-adds opt-in
 * client-side sorting for every `table.wikitable` inside
 * `.mw-parser-output`.
 *
 * Behavior:
 *   - Header cells (thead th OR first-row th OR tr.wikitable2R th/td)
 *     become clickable. A small ↕ / ▲ / ▼ indicator appears next to
 *     the header label.
 *   - 1st click → ascending. 2nd click on the SAME column → descending.
 *     3rd click → restore original row order (cleared sort).
 *   - Numeric cells parse first; if parse fails for any row, falls
 *     back to localeCompare string sort.
 *   - Sort is stable: original row index is captured at init and
 *     used as the tie-breaker.
 *   - HTML structure of <tr> / <th> is preserved (no rewriting of
 *     captions, classes, colspans). Only event listeners and a
 *     `<span class="sort-indicator">` are added.
 *
 * Loaded via <script defer src="../assets/wikitable_sort.js"> from
 * build_v2.py's HTML template.
 */
(function () {
  'use strict';

  /* Parse a cell into a sort key. Returns { num, str } — sort uses
     num if BOTH cells in a comparison parsed as numbers, otherwise
     falls back to str.localeCompare. */
  function cellKey(cell) {
    if (!cell) return { num: NaN, str: '' };
    // Use textContent so nested <a>/<span> still contribute their text.
    var raw = (cell.textContent || '').trim();
    // Strip common decorations: thousands separators, leading +, trailing
    // unit suffixes like "ft." "环" — keep first token for number parse.
    var firstTok = raw.replace(/,/g, '').match(/-?\d+(?:\.\d+)?/);
    var num = firstTok ? parseFloat(firstTok[0]) : NaN;
    return { num: num, str: raw };
  }

  /* Locate the header row of a wikitable. Three patterns are seen
     in the huiji corpus:
       1. <thead><tr><th>...</th></tr></thead>
       2. <tbody><tr class="wikitable2R"><th>...</th>...</tr>  (huiji idiom)
       3. <tbody><tr><th>...</th></tr>                         (bare first-row)
     Returns { row, cells, container, bodyRows } or null. */
  function findHeader(table) {
    var thead = table.querySelector(':scope > thead');
    if (thead) {
      var hr = thead.querySelector('tr');
      if (hr) {
        var ths = hr.querySelectorAll('th');
        if (ths.length > 0) {
          var tbody = table.querySelector(':scope > tbody');
          var rows = tbody ? Array.prototype.slice.call(tbody.children).filter(function (n) { return n.tagName === 'TR'; }) : [];
          return { row: hr, cells: ths, container: tbody || table, bodyRows: rows };
        }
      }
    }
    // No <thead> — fall back to first <tr> in <tbody> (or table).
    var tbody2 = table.querySelector(':scope > tbody') || table;
    var rows2 = Array.prototype.slice.call(tbody2.children).filter(function (n) { return n.tagName === 'TR'; });
    if (rows2.length < 2) return null;  // need at least header + 1 data row
    var first = rows2[0];
    // Header row recognized either by class wikitable2R OR by having
    // any <th> child.
    var hasTh = first.querySelector('th');
    var isHuiji = first.classList.contains('wikitable2R');
    if (!hasTh && !isHuiji) return null;
    // For wikitable2R rows huiji sometimes uses <td> as headers — accept both.
    var headerCells = first.querySelectorAll(isHuiji && !hasTh ? 'td' : 'th');
    if (headerCells.length === 0) return null;
    return { row: first, cells: headerCells, container: tbody2, bodyRows: rows2.slice(1) };
  }

  function decorate(table, hdr) {
    // Capture original order for restore (3rd click) AND stable tie-break.
    hdr.bodyRows.forEach(function (tr, i) { tr.__wtOrigIdx = i; });

    // State: which col is sorted, in which direction (null/'asc'/'desc').
    var state = { col: -1, dir: null };

    Array.prototype.forEach.call(hdr.cells, function (th, colIdx) {
      th.classList.add('sortable');
      // Inject indicator span (after existing content so links/strong stay clickable).
      var ind = document.createElement('span');
      ind.className = 'sort-indicator';
      ind.textContent = ' ↕';  // ↕
      ind.setAttribute('aria-hidden', 'true');
      th.appendChild(ind);

      th.addEventListener('click', function (e) {
        // Don't hijack clicks that land on a nested <a> (links should still navigate).
        var t = e.target;
        while (t && t !== th) {
          if (t.tagName === 'A') return;
          t = t.parentNode;
        }
        sortBy(colIdx);
      });
    });

    function sortBy(colIdx) {
      // Cycle: asc → desc → none → asc …  (per-column; switching column
      // resets the cycle to asc).
      var nextDir;
      if (state.col !== colIdx) {
        nextDir = 'asc';
      } else if (state.dir === 'asc') {
        nextDir = 'desc';
      } else if (state.dir === 'desc') {
        nextDir = null;
      } else {
        nextDir = 'asc';
      }
      state.col = colIdx;
      state.dir = nextDir;

      // Update header chrome.
      Array.prototype.forEach.call(hdr.cells, function (th, i) {
        th.classList.remove('sorted-asc', 'sorted-desc');
        var ind = th.querySelector(':scope > .sort-indicator');
        if (!ind) return;
        if (i === colIdx && nextDir === 'asc')  { th.classList.add('sorted-asc');  ind.textContent = ' ▲'; }
        else if (i === colIdx && nextDir === 'desc') { th.classList.add('sorted-desc'); ind.textContent = ' ▼'; }
        else { ind.textContent = ' ↕'; }
      });

      // Build sorted copy of bodyRows.
      var sorted = hdr.bodyRows.slice();

      if (nextDir === null) {
        // Restore original.
        sorted.sort(function (a, b) { return a.__wtOrigIdx - b.__wtOrigIdx; });
      } else {
        // Decide numeric vs string by MAJORITY: if most non-empty cells parse as
        // numbers, sort numerically (one stray '—'/CJK cell shouldn't force lexical
        // sort, e.g. creature-level columns). Non-numeric cells sort to the end.
        var numCnt = 0, nonEmpty = 0;
        var keys = sorted.map(function (tr) {
          var cell = tr.children[colIdx];
          var k = cellKey(cell);
          var s = (k.str || '').trim();
          if (s) { nonEmpty++; if (!isNaN(k.num)) numCnt++; }
          return k;
        });
        var allNum = nonEmpty > 0 && numCnt >= nonEmpty * 0.7;

        var dirMul = (nextDir === 'asc') ? 1 : -1;
        var idx = sorted.map(function (tr, i) { return i; });
        idx.sort(function (i, j) {
          var ka = keys[i], kb = keys[j];
          var cmp;
          if (allNum) {
            // NaN (non-numeric) cells sort to the end regardless of direction.
            var an = isNaN(ka.num), bn = isNaN(kb.num);
            if (an && bn) cmp = 0;
            else if (an) return 1;
            else if (bn) return -1;
            else cmp = ka.num - kb.num;
          } else {
            cmp = ka.str.localeCompare(kb.str, 'zh-Hans-CN', { numeric: true });
          }
          if (cmp !== 0) return cmp * dirMul;
          // Stable tie-break by original position.
          return sorted[i].__wtOrigIdx - sorted[j].__wtOrigIdx;
        });
        sorted = idx.map(function (i) { return sorted[i]; });
      }

      // Re-append in new order. appendChild moves the node (no clone).
      var frag = document.createDocumentFragment();
      sorted.forEach(function (tr) { frag.appendChild(tr); });
      hdr.container.appendChild(frag);
    }
  }

  function init() {
    var tables = document.querySelectorAll('.mw-parser-output table.wikitable');
    for (var i = 0; i < tables.length; i++) {
      try {
        var hdr = findHeader(tables[i]);
        if (!hdr) continue;
        if (hdr.bodyRows.length < 2) continue;  // nothing to sort
        decorate(tables[i], hdr);
      } catch (e) {
        if (window.console && console.error) {
          console.error('[wikitable_sort] failed for table', i, e);
        }
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
