/* ============================================================
   filter.js — Phase 6, Agent FILT
   Client-side filter chips for AoN-style tables.

   Coordinates with Agent TABLE: the builder emits an empty
   <div class="aon-filter-bar" data-filter-table="#..."></div>
   directly above each browse table; this script discovers each
   bar on DOMContentLoaded, scans the linked table's <tbody> rows
   for facet values (source / rarity / level / trait), generates
   chip <button>s grouped by facet, and wires click handlers that
   recompute row visibility plus an "X / Y rows" counter.

   Filter algebra:
     AND between groups, OR within a group.
     A row is visible iff for EACH group that has >=1 active chip,
     the row matches at least one active chip in that group.
     A group with zero active chips imposes no constraint.

   Data contract on <tr>:
     - data-source   e.g. "PC2"
     - data-rarity   e.g. "常见" / "罕见" / "稀有" / "独特"
     - data-level    integer string, e.g. "0", "5", "21"
     - data-traits   comma-separated, e.g. "通用,技能"
   Missing attributes are simply not faceted on for that row.

   No external deps. Vanilla ES2018.
   ============================================================ */

(function () {
  'use strict';

  // Level buckets (low inclusive, high inclusive; null high = open)
  var LEVEL_BUCKETS = [
    { key: '0-1',   label: '0-1',   lo: 0,  hi: 1   },
    { key: '2-5',   label: '2-5',   lo: 2,  hi: 5   },
    { key: '6-10',  label: '6-10',  lo: 6,  hi: 10  },
    { key: '11-15', label: '11-15', lo: 11, hi: 15  },
    { key: '16-20', label: '16-20', lo: 16, hi: 20  },
    { key: '21+',   label: '21+',   lo: 21, hi: null }
  ];

  var GROUP_LABELS = {
    source: '来源',   // 来源
    rarity: '稀有度', // 稀有度
    level:  '等级',   // 等级
    trait:  '特质'    // 特质
  };

  // Stable display order within a group (others sorted by count desc)
  var RARITY_ORDER = ['常见','罕见','稀有','独特']; // 常见 罕见 稀有 独特

  // Top-N trait chips per table (keep UI compact)
  var TRAIT_TOP_N = 20;

  function ready(fn) {
    if (document.readyState !== 'loading') { fn(); }
    else { document.addEventListener('DOMContentLoaded', fn); }
  }

  function getRows(table) {
    if (!table) return [];
    var tbody = table.tBodies && table.tBodies[0];
    var rows = tbody ? tbody.rows : table.rows;
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      // Skip header-style rows
      if (r.cells.length === 0) continue;
      if (r.querySelector('th') && !r.querySelector('td')) continue;
      out.push(r);
    }
    return out;
  }

  function rowLevelBucket(lvl) {
    if (lvl === null || isNaN(lvl)) return null;
    for (var i = 0; i < LEVEL_BUCKETS.length; i++) {
      var b = LEVEL_BUCKETS[i];
      if (lvl >= b.lo && (b.hi === null || lvl <= b.hi)) return b.key;
    }
    return null;
  }

  function parseTraits(s) {
    if (!s) return [];
    return s.split(',').map(function (t) { return t.trim(); }).filter(Boolean);
  }

  function scan(rows) {
    var counts = { source: {}, rarity: {}, level: {}, trait: {} };
    var hasGroup = { source: false, rarity: false, level: false, trait: false };
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var src = r.getAttribute('data-source');
      var rar = r.getAttribute('data-rarity');
      var lvlStr = r.getAttribute('data-level');
      var traitsStr = r.getAttribute('data-traits');

      if (src) { counts.source[src] = (counts.source[src] || 0) + 1; hasGroup.source = true; }
      if (rar) { counts.rarity[rar] = (counts.rarity[rar] || 0) + 1; hasGroup.rarity = true; }
      if (lvlStr !== null && lvlStr !== '') {
        var lvl = parseInt(lvlStr, 10);
        var bucket = rowLevelBucket(lvl);
        if (bucket) { counts.level[bucket] = (counts.level[bucket] || 0) + 1; hasGroup.level = true; }
      }
      if (traitsStr) {
        var ts = parseTraits(traitsStr);
        for (var j = 0; j < ts.length; j++) {
          counts.trait[ts[j]] = (counts.trait[ts[j]] || 0) + 1;
        }
        if (ts.length) hasGroup.trait = true;
      }
    }
    return { counts: counts, hasGroup: hasGroup };
  }

  function sortedKeys(group, counts) {
    var keys = Object.keys(counts);
    if (group === 'level') {
      // Preserve LEVEL_BUCKETS order
      return LEVEL_BUCKETS.map(function (b) { return b.key; })
                          .filter(function (k) { return counts[k]; });
    }
    if (group === 'rarity') {
      var seen = {};
      var ordered = RARITY_ORDER.filter(function (k) {
        if (counts[k]) { seen[k] = 1; return true; }
        return false;
      });
      // Append any non-canonical rarity tokens (defensive)
      keys.sort(function (a, b) { return counts[b] - counts[a]; });
      keys.forEach(function (k) { if (!seen[k]) ordered.push(k); });
      return ordered;
    }
    // source / trait: by count desc, then alpha
    keys.sort(function (a, b) {
      if (counts[b] !== counts[a]) return counts[b] - counts[a];
      return a < b ? -1 : (a > b ? 1 : 0);
    });
    if (group === 'trait' && keys.length > TRAIT_TOP_N) {
      keys = keys.slice(0, TRAIT_TOP_N);
    }
    return keys;
  }

  function buildGroup(bar, group, counts) {
    var keys = sortedKeys(group, counts);
    if (!keys.length) return null;
    var wrap = document.createElement('div');
    wrap.className = 'filter-group';
    wrap.setAttribute('data-filter-col', group);

    var label = document.createElement('span');
    label.className = 'filter-group-label';
    label.textContent = GROUP_LABELS[group] || group;
    wrap.appendChild(label);

    for (var i = 0; i < keys.length; i++) {
      var v = keys[i];
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'filter-chip';
      btn.setAttribute('data-value', v);
      var displayLabel = (group === 'level') ? labelForLevel(v) : v;
      btn.textContent = displayLabel + ' (' + counts[v] + ')';
      wrap.appendChild(btn);
    }
    bar.appendChild(wrap);
    return wrap;
  }

  function labelForLevel(key) {
    for (var i = 0; i < LEVEL_BUCKETS.length; i++) {
      if (LEVEL_BUCKETS[i].key === key) return LEVEL_BUCKETS[i].label;
    }
    return key;
  }

  function activeChipsByGroup(bar) {
    var groups = bar.querySelectorAll('.filter-group');
    var state = {};
    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      var col = g.getAttribute('data-filter-col');
      var act = g.querySelectorAll('.filter-chip.active');
      if (!act.length) continue;
      var vals = [];
      for (var j = 0; j < act.length; j++) vals.push(act[j].getAttribute('data-value'));
      state[col] = vals;
    }
    return state;
  }

  function rowMatches(row, active) {
    for (var col in active) {
      if (!Object.prototype.hasOwnProperty.call(active, col)) continue;
      var wanted = active[col];
      var rowVal = null;
      if (col === 'source')      rowVal = [row.getAttribute('data-source') || ''];
      else if (col === 'rarity') rowVal = [row.getAttribute('data-rarity') || ''];
      else if (col === 'level') {
        var s = row.getAttribute('data-level');
        if (s === null || s === '') return false;
        var n = parseInt(s, 10);
        var b = rowLevelBucket(n);
        rowVal = b ? [b] : [];
      }
      else if (col === 'trait') {
        rowVal = parseTraits(row.getAttribute('data-traits'));
      }
      if (!rowVal || !rowVal.length) return false;
      var ok = false;
      for (var i = 0; i < wanted.length && !ok; i++) {
        for (var j = 0; j < rowVal.length && !ok; j++) {
          if (wanted[i] === rowVal[j]) ok = true;
        }
      }
      if (!ok) return false;
    }
    return true;
  }

  function applyFilters(bar, rows, counter, total) {
    var active = activeChipsByGroup(bar);
    var shown = 0;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var match = rowMatches(r, active);
      r.style.display = match ? '' : 'none';
      if (match) shown++;
    }
    if (counter) {
      counter.textContent = shown + ' / ' + total + ' 行'; // 行
    }
  }

  function attachHandlers(bar, rows, counter, total) {
    bar.addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.classList && t.classList.contains('filter-chip')) {
        t.classList.toggle('active');
        applyFilters(bar, rows, counter, total);
      } else if (t && t.classList && t.classList.contains('filter-reset')) {
        var chips = bar.querySelectorAll('.filter-chip.active');
        for (var i = 0; i < chips.length; i++) chips[i].classList.remove('active');
        applyFilters(bar, rows, counter, total);
      }
    });
  }

  function buildBar(bar) {
    var sel = bar.getAttribute('data-filter-table');
    if (!sel) return;
    var table = document.querySelector(sel);
    if (!table) return;
    var rows = getRows(table);
    if (!rows.length) return;

    var info = scan(rows);
    bar.innerHTML = ''; // wipe placeholder content

    // Build groups in canonical order
    var order = ['source', 'rarity', 'level', 'trait'];
    for (var i = 0; i < order.length; i++) {
      if (info.hasGroup[order[i]]) buildGroup(bar, order[i], info.counts[order[i]]);
    }

    // Counter + reset
    var tail = document.createElement('div');
    tail.className = 'filter-tail';

    var counter = document.createElement('span');
    counter.className = 'filter-counter';
    counter.textContent = rows.length + ' / ' + rows.length + ' 行';
    tail.appendChild(counter);

    var reset = document.createElement('button');
    reset.type = 'button';
    reset.className = 'filter-reset';
    reset.textContent = '清除筛选'; // 清除筛选
    tail.appendChild(reset);

    bar.appendChild(tail);

    attachHandlers(bar, rows, counter, rows.length);
  }

  ready(function () {
    var bars = document.querySelectorAll('.aon-filter-bar');
    for (var i = 0; i < bars.length; i++) buildBar(bars[i]);
  });
})();
