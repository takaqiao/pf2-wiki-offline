/* PF2 offline wiki — client-side full-text search.
 *
 * Loads:
 *   titles.js   (in-memory: every page's id/title/href/excerpt)
 *   manifest.js (lists available shards)
 *   shards/b_XX.js, shards/w_X.js (lazy on demand, JSONP-style)
 *
 * Public entry points:
 *   PF2Search.init({ root, onReady, onError })
 *   PF2Search.query(text, { limit }) → Promise<results>
 *
 * Loader strategy: all data files are JS that, when loaded, register their
 * payload on the global. We use <script> injection because `file://` `fetch`
 * is unreliable across browsers.
 */
(function () {
  "use strict";

  const W = window;
  W.PF2Search = W.PF2Search || {};

  /* ---------------- registry ---------------- */
  // titles.js fills this:
  //   window.__PF2_TITLES = { v:1, items: [ {i,t,h,k,e}, ... ] }
  // manifest.js fills this:
  //   window.__PF2_MANIFEST = { v:1, n_pages, bigram_shards: [...], word_shards: [...] }
  // shards/*.js call these registrars:
  const _bgShards = Object.create(null);   // bucket -> { bigram: [ids] }
  const _wShards  = Object.create(null);   // bucket -> { word:   [ids] }
  const _bgLoading = Object.create(null);  // bucket -> Promise
  const _wLoading  = Object.create(null);

  W.__PF2_SHARD_B = function (bucket, payload) {
    _bgShards[bucket] = payload;
    const p = _bgLoading[bucket];
    if (p && p._resolve) p._resolve();
  };
  W.__PF2_SHARD_W = function (bucket, payload) {
    _wShards[bucket] = payload;
    const p = _wLoading[bucket];
    if (p && p._resolve) p._resolve();
  };

  /* ---------------- script loader ---------------- */
  function loadScript(url) {
    return new Promise(function (resolve, reject) {
      const s = document.createElement("script");
      s.src = url;
      s.async = true;
      s.onload = function () { resolve(url); };
      s.onerror = function () { reject(new Error("Failed to load " + url)); };
      document.head.appendChild(s);
    });
  }

  /* ---------------- char classification ---------------- */
  function isCJK(cp) {
    return (cp >= 0x3400 && cp <= 0x4DBF)
        || (cp >= 0x4E00 && cp <= 0x9FFF)
        || (cp >= 0xF900 && cp <= 0xFAFF)
        || (cp >= 0x20000 && cp <= 0x2A6DF);
  }
  function isCJKch(ch) { return isCJK(ch.codePointAt(0)); }

  /* ---------------- bucket helpers (must mirror Python) ---------------- */
  // md5 first byte hex, using a tiny inline md5. We need this only for bigrams.
  // Implementation: standard md5 over UTF-8 bytes.
  function _md5_b0(s) {
    // Use TextEncoder when available
    const bytes = (typeof TextEncoder !== "undefined")
      ? new TextEncoder().encode(s)
      : _utf8Bytes(s);
    return md5FirstByteHex(bytes);
  }
  function _utf8Bytes(s) {
    const out = [];
    for (let i = 0; i < s.length; i++) {
      let cp = s.charCodeAt(i);
      if (cp < 0x80) out.push(cp);
      else if (cp < 0x800) { out.push(0xc0 | (cp >> 6)); out.push(0x80 | (cp & 0x3f)); }
      else if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < s.length) {
        const cp2 = s.charCodeAt(i + 1);
        const u = 0x10000 + (((cp & 0x3ff) << 10) | (cp2 & 0x3ff));
        out.push(0xf0 | (u >> 18));
        out.push(0x80 | ((u >> 12) & 0x3f));
        out.push(0x80 | ((u >> 6) & 0x3f));
        out.push(0x80 | (u & 0x3f));
        i++;
      } else {
        out.push(0xe0 | (cp >> 12));
        out.push(0x80 | ((cp >> 6) & 0x3f));
        out.push(0x80 | (cp & 0x3f));
      }
    }
    return out;
  }

  // ---- Tiny MD5 (returns first byte as hex string) -----------------------
  // Adapted from public-domain MD5 implementations. We only expose the first
  // output byte, which is what our bucket function needs.
  function md5FirstByteHex(bytes) {
    const a = md5Bytes(bytes);
    return ("0" + a[0].toString(16)).slice(-2);
  }
  function md5Bytes(bytes) {
    const len = bytes.length;
    const nblocks = ((len + 8) >> 6) + 1;
    const total = nblocks * 16;
    const x = new Uint32Array(total);
    for (let i = 0; i < len; i++) {
      x[i >> 2] |= bytes[i] << ((i & 3) * 8);
    }
    x[len >> 2] |= 0x80 << ((len & 3) * 8);
    x[total - 2] = len * 8;
    let a = 1732584193, b = -271733879, c = -1732584194, d = 271733878;
    for (let i = 0; i < total; i += 16) {
      const olda = a, oldb = b, oldc = c, oldd = d;
      a = ff(a, b, c, d, x[i+ 0], 7, -680876936);
      d = ff(d, a, b, c, x[i+ 1], 12, -389564586);
      c = ff(c, d, a, b, x[i+ 2], 17, 606105819);
      b = ff(b, c, d, a, x[i+ 3], 22, -1044525330);
      a = ff(a, b, c, d, x[i+ 4], 7, -176418897);
      d = ff(d, a, b, c, x[i+ 5], 12, 1200080426);
      c = ff(c, d, a, b, x[i+ 6], 17, -1473231341);
      b = ff(b, c, d, a, x[i+ 7], 22, -45705983);
      a = ff(a, b, c, d, x[i+ 8], 7, 1770035416);
      d = ff(d, a, b, c, x[i+ 9], 12, -1958414417);
      c = ff(c, d, a, b, x[i+10], 17, -42063);
      b = ff(b, c, d, a, x[i+11], 22, -1990404162);
      a = ff(a, b, c, d, x[i+12], 7, 1804603682);
      d = ff(d, a, b, c, x[i+13], 12, -40341101);
      c = ff(c, d, a, b, x[i+14], 17, -1502002290);
      b = ff(b, c, d, a, x[i+15], 22, 1236535329);

      a = gg(a, b, c, d, x[i+ 1], 5, -165796510);
      d = gg(d, a, b, c, x[i+ 6], 9, -1069501632);
      c = gg(c, d, a, b, x[i+11], 14, 643717713);
      b = gg(b, c, d, a, x[i+ 0], 20, -373897302);
      a = gg(a, b, c, d, x[i+ 5], 5, -701558691);
      d = gg(d, a, b, c, x[i+10], 9, 38016083);
      c = gg(c, d, a, b, x[i+15], 14, -660478335);
      b = gg(b, c, d, a, x[i+ 4], 20, -405537848);
      a = gg(a, b, c, d, x[i+ 9], 5, 568446438);
      d = gg(d, a, b, c, x[i+14], 9, -1019803690);
      c = gg(c, d, a, b, x[i+ 3], 14, -187363961);
      b = gg(b, c, d, a, x[i+ 8], 20, 1163531501);
      a = gg(a, b, c, d, x[i+13], 5, -1444681467);
      d = gg(d, a, b, c, x[i+ 2], 9, -51403784);
      c = gg(c, d, a, b, x[i+ 7], 14, 1735328473);
      b = gg(b, c, d, a, x[i+12], 20, -1926607734);

      a = hh(a, b, c, d, x[i+ 5], 4, -378558);
      d = hh(d, a, b, c, x[i+ 8], 11, -2022574463);
      c = hh(c, d, a, b, x[i+11], 16, 1839030562);
      b = hh(b, c, d, a, x[i+14], 23, -35309556);
      a = hh(a, b, c, d, x[i+ 1], 4, -1530992060);
      d = hh(d, a, b, c, x[i+ 4], 11, 1272893353);
      c = hh(c, d, a, b, x[i+ 7], 16, -155497632);
      b = hh(b, c, d, a, x[i+10], 23, -1094730640);
      a = hh(a, b, c, d, x[i+13], 4, 681279174);
      d = hh(d, a, b, c, x[i+ 0], 11, -358537222);
      c = hh(c, d, a, b, x[i+ 3], 16, -722521979);
      b = hh(b, c, d, a, x[i+ 6], 23, 76029189);
      a = hh(a, b, c, d, x[i+ 9], 4, -640364487);
      d = hh(d, a, b, c, x[i+12], 11, -421815835);
      c = hh(c, d, a, b, x[i+15], 16, 530742520);
      b = hh(b, c, d, a, x[i+ 2], 23, -995338651);

      a = ii(a, b, c, d, x[i+ 0], 6, -198630844);
      d = ii(d, a, b, c, x[i+ 7], 10, 1126891415);
      c = ii(c, d, a, b, x[i+14], 15, -1416354905);
      b = ii(b, c, d, a, x[i+ 5], 21, -57434055);
      a = ii(a, b, c, d, x[i+12], 6, 1700485571);
      d = ii(d, a, b, c, x[i+ 3], 10, -1894986606);
      c = ii(c, d, a, b, x[i+10], 15, -1051523);
      b = ii(b, c, d, a, x[i+ 1], 21, -2054922799);
      a = ii(a, b, c, d, x[i+ 8], 6, 1873313359);
      d = ii(d, a, b, c, x[i+15], 10, -30611744);
      c = ii(c, d, a, b, x[i+ 6], 15, -1560198380);
      b = ii(b, c, d, a, x[i+13], 21, 1309151649);
      a = ii(a, b, c, d, x[i+ 4], 6, -145523070);
      d = ii(d, a, b, c, x[i+11], 10, -1120210379);
      c = ii(c, d, a, b, x[i+ 2], 15, 718787259);
      b = ii(b, c, d, a, x[i+ 9], 21, -343485551);

      a = safeAdd(a, olda);
      b = safeAdd(b, oldb);
      c = safeAdd(c, oldc);
      d = safeAdd(d, oldd);
    }
    // Return first 4 bytes (little-endian) of state `a`
    return [a & 0xff, (a >>> 8) & 0xff, (a >>> 16) & 0xff, (a >>> 24) & 0xff];
  }
  function safeAdd(x, y) {
    const lsw = (x & 0xffff) + (y & 0xffff);
    const msw = (x >>> 16) + (y >>> 16) + (lsw >>> 16);
    return ((msw & 0xffff) << 16) | (lsw & 0xffff);
  }
  function rol(n, c) { return (n << c) | (n >>> (32 - c)); }
  function cmn(q, a, b, x, s, t) {
    return safeAdd(rol(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b);
  }
  function ff(a,b,c,d,x,s,t){ return cmn((b & c) | ((~b) & d), a, b, x, s, t); }
  function gg(a,b,c,d,x,s,t){ return cmn((b & d) | (c & (~d)), a, b, x, s, t); }
  function hh(a,b,c,d,x,s,t){ return cmn(b ^ c ^ d, a, b, x, s, t); }
  function ii(a,b,c,d,x,s,t){ return cmn(c ^ (b | (~d)), a, b, x, s, t); }

  function bigramBucket(bg) { return _md5_b0(bg); }
  function wordBucket(w) {
    const c = w.charCodeAt(0);
    if (c >= 97 && c <= 122) return w[0];
    return "_";
  }

  /* ---------------- lazy shard fetcher ---------------- */
  function ensureBigramShard(bucket) {
    if (_bgShards[bucket]) return Promise.resolve();
    if (_bgLoading[bucket]) return _bgLoading[bucket];
    const url = state.root + "shards/b_" + bucket + ".js";
    const promise = new Promise(function (resolve, reject) {
      const p = loadScript(url);
      // resolution actually happens inside __PF2_SHARD_B; loadScript only
      // tells us the network step succeeded. But if the bucket file doesn't
      // exist (e.g. nothing hashes to this byte in a small fixture), mark it
      // empty so we don't retry.
      p.then(function () {
        if (!_bgShards[bucket]) _bgShards[bucket] = {};
        resolve();
      }).catch(function () {
        // No shard for that bucket — treat as empty.
        _bgShards[bucket] = {};
        resolve();
      });
    });
    _bgLoading[bucket] = promise;
    return promise;
  }
  function ensureWordShard(bucket) {
    if (_wShards[bucket]) return Promise.resolve();
    if (_wLoading[bucket]) return _wLoading[bucket];
    const url = state.root + "shards/w_" + bucket + ".js";
    const promise = new Promise(function (resolve, reject) {
      loadScript(url).then(function () {
        if (!_wShards[bucket]) _wShards[bucket] = {};
        resolve();
      }).catch(function () {
        _wShards[bucket] = {};
        resolve();
      });
    });
    _wLoading[bucket] = promise;
    return promise;
  }

  /* ---------------- query parsing ---------------- */
  function parseQuery(q) {
    // Returns { cjk: [bigrams or unigrams], latin: [words], titleRaw }
    const out = { cjk: [], latin: [], titleRaw: q.trim().toLowerCase() };
    if (!q) return out;
    // Split into CJK runs and Latin words
    let i = 0;
    while (i < q.length) {
      const ch = q[i];
      if (isCJKch(ch)) {
        // collect run
        let j = i;
        while (j < q.length && isCJKch(q[j])) j++;
        const run = q.slice(i, j);
        if (run.length === 1) {
          out.cjk.push(run);  // unigram fallback
        } else {
          for (let k = 0; k < run.length - 1; k++) {
            out.cjk.push(run.slice(k, k + 2));
          }
        }
        i = j;
      } else if (/[A-Za-z0-9]/.test(ch)) {
        let j = i;
        while (j < q.length && /[A-Za-z0-9_'-]/.test(q[j])) j++;
        const w = q.slice(i, j).toLowerCase();
        if (w.length >= 2) out.latin.push(w);
        i = j;
      } else {
        i++;
      }
    }
    return out;
  }

  /* ---------------- intersection ---------------- */
  function intersectSorted(a, b) {
    // Both are sorted ascending arrays of page ids.
    const out = [];
    let i = 0, j = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { out.push(a[i]); i++; j++; }
      else if (a[i] < b[j]) i++;
      else j++;
    }
    return out;
  }

  /* ---------------- search core ---------------- */
  const state = {
    ready: false,
    root: "",        // e.g. "./" or "../index/"
    items: null,     // titles array
    byId: null,      // id -> item lookup (identity since ids are array indices)
  };

  function init(opts) {
    return new Promise(function (resolve, reject) {
      state.root = (opts && opts.root) || "./";
      if (!state.root.endsWith("/")) state.root += "/";
      Promise.all([
        loadScript(state.root + "manifest.js"),
        loadScript(state.root + "titles.js"),
        // types.js is optional — search still works without it (just no badges).
        loadScript(state.root + "types.js").catch(function () { return null; }),
      ]).then(function () {
        const t = W.__PF2_TITLES;
        if (!t || !t.items) {
          reject(new Error("titles.js loaded but did not register data"));
          return;
        }
        state.items = t.items;
        state.byId = state.items;  // i === array index by construction
        // Optional parallel popularity array (inbound-link counts) emitted by
        // build_search_v2.py. Used as the secondary sort key — when two hits
        // share a relevance score, the more-linked-to page wins (so "战士"
        // outranks "战士专长(2e)" because the bare class page is linked far
        // more often). Falls back to all-zero when absent (older index).
        state.popularity = (Array.isArray(t.pop) && t.pop.length === state.items.length)
          ? t.pop : null;
        // Optional aligned type lookup (window.__PF2_TYPES). If present, each
        // character in .codes corresponds 1:1 to items[i].
        const types = W.__PF2_TYPES;
        if (types && typeof types.codes === "string"
            && types.codes.length === state.items.length) {
          state.typeCodes = types.codes;
          state.typeLegend = types.legend || {};
        } else {
          state.typeCodes = null;
          state.typeLegend = {};
        }
        state.ready = true;
        if (opts && opts.onReady) opts.onReady({ n_pages: state.items.length });
        resolve(state);
      }).catch(function (e) {
        if (opts && opts.onError) opts.onError(e);
        reject(e);
      });
    });
  }

  /* ---------------- type resolution ---------------- */
  // Map type code (single char) to friendly name + CSS class slug + Chinese label.
  // Kept in sync with build_types_index.py.
  const TYPE_INFO = {
    feat:       { label: "专长",   className: "kind-feat",      order: 2 },
    spell:      { label: "法术",   className: "kind-spell",     order: 1 },
    creature:   { label: "生物",   className: "kind-creature",  order: 3 },
    item:       { label: "物品",   className: "kind-item",      order: 4 },
    condition:  { label: "状态",   className: "kind-condition", order: 5 },
    ancestry:   { label: "族裔",   className: "kind-ancestry",  order: 6 },
    class:      { label: "职业",   className: "kind-class",     order: 7 },
    background: { label: "背景",   className: "kind-background",order: 8 },
    location:   { label: "地理",   className: "kind-location",  order: 9 },
    deity:      { label: "信仰",   className: "kind-deity",     order: 10 },
    action:     { label: "动作",   className: "kind-action",    order: 11 },
    trait:      { label: "特征",   className: "kind-trait",     order: 12 },
    stub:       { label: "短条目", className: "kind-stub",      order: 13 },
    other:      { label: "其他",   className: "kind-other",     order: 14 },
  };

  function resolveType(item) {
    // 1. Lookup via aligned type-code string (fast path).
    if (state.typeCodes && typeof item.i === "number"
        && item.i >= 0 && item.i < state.typeCodes.length) {
      const code = state.typeCodes[item.i];
      const name = state.typeLegend[code];
      if (name && TYPE_INFO[name]) return name;
    }
    // 2. Fallback: slug-prefix heuristic for Data: pages.
    if (item.k === "d") {
      const decoded = (function () {
        try { return decodeURIComponent(item.h || ""); }
        catch (e) { return item.h || ""; }
      })();
      const head = decoded.split("-", 1)[0];
      if (head === "Conditions") return "condition";
      if (head === "Spells")     return "spell";
      if (head === "Creatures")  return "creature";
      if (head === "Feats")      return "feat";
      if (head === "Items")      return "item";
      if (head === "Traits")     return "trait";
    }
    return "other";
  }

  async function query(text, opts) {
    opts = opts || {};
    const limit = opts.limit || 50;
    if (!state.ready) throw new Error("PF2Search not initialised");
    const p = parseQuery(text);
    if (!p.cjk.length && !p.latin.length) return [];

    // Determine which shards we need
    const bgBuckets = new Set();
    for (const bg of p.cjk) bgBuckets.add(bigramBucket(bg));
    const wBuckets = new Set();
    for (const w of p.latin) wBuckets.add(wordBucket(w));

    await Promise.all([
      ...Array.from(bgBuckets).map(ensureBigramShard),
      ...Array.from(wBuckets).map(ensureWordShard),
    ]);

    // Collect posting lists per token
    const lists = [];
    for (const bg of p.cjk) {
      const sh = _bgShards[bigramBucket(bg)];
      const ids = sh ? sh[bg] : null;
      // unigram fallback if length 1 (no bigram)
      if (ids && ids.length) lists.push(ids);
    }
    for (const w of p.latin) {
      const sh = _wShards[wordBucket(w)];
      // Exact match first; if missing, attempt prefix scan within bucket.
      if (sh && sh[w]) {
        lists.push(sh[w]);
      } else if (sh) {
        // prefix scan
        const merged = [];
        const seen = new Set();
        for (const key in sh) {
          if (key.startsWith(w)) {
            for (const id of sh[key]) {
              if (!seen.has(id)) { seen.add(id); merged.push(id); }
            }
          }
        }
        if (merged.length) {
          merged.sort(function (a, b) { return a - b; });
          lists.push(merged);
        }
      }
    }

    // If no list produced results, fall back to title substring match.
    let candidates;
    if (!lists.length) {
      candidates = titleSubstringSearch(text);
    } else {
      // Intersect from smallest to largest for performance
      lists.sort(function (a, b) { return a.length - b.length; });
      candidates = lists[0].slice();
      for (let i = 1; i < lists.length && candidates.length; i++) {
        candidates = intersectSorted(candidates, lists[i]);
      }
      // Always *union* with raw title substring matches — captures titles
      // that include the query verbatim even if the inverted index missed
      // them (e.g. very short query, mixed CJK+latin).
      const ts = titleSubstringSearch(text);
      const have = new Set(candidates);
      for (const id of ts) {
        if (!have.has(id)) candidates.push(id);
      }
    }

    // Rank: title-prefix > title-substring > content-only.
    const lower = text.toLowerCase().trim();
    const pop = state.popularity;  // may be null on legacy indexes
    const ranked = candidates.map(function (id) {
      const it = state.byId[id];
      const tl = (it.t || "").toLowerCase();
      let score = 0;
      if (tl === lower) score += 1000;
      else if (tl.startsWith(lower)) score += 500;
      else if (tl.indexOf(lower) >= 0) score += 200;
      // Shorter titles score higher (more relevant for direct matches)
      score -= Math.min(50, (it.t || "").length);
      // Namespace boost: main content > data
      if (it.k === "p") score += 5;
      // Inbound-link popularity — used only as a tiebreaker, NOT folded into
      // `score` so it can't outweigh title-match boosts. Stored alongside on
      // the result row and consulted by the comparator below.
      const popVal = (pop && typeof id === "number") ? (pop[id] | 0) : 0;
      return { item: it, score: score, pop: popVal };
    });
    // Primary sort: relevance score (desc). Secondary: inbound-link count
    // (desc) so canonical pages float above their disambiguation siblings.
    // Tertiary: id (asc) for stable ordering when both are equal.
    ranked.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      if (b.pop !== a.pop) return b.pop - a.pop;
      return (a.item.i | 0) - (b.item.i | 0);
    });

    return ranked.slice(0, limit).map(function (r) {
      return {
        id: r.item.i,
        title: r.item.t,
        href: r.item.h,
        kind: r.item.k,
        type: resolveType(r.item),
        excerpt: r.item.e || "",
        score: r.score,
      };
    });
  }

  function titleSubstringSearch(q) {
    const lower = q.toLowerCase().trim();
    if (!lower) return [];
    const out = [];
    const items = state.items;
    for (let i = 0; i < items.length; i++) {
      if ((items[i].t || "").toLowerCase().indexOf(lower) >= 0) {
        out.push(items[i].i);
      }
    }
    return out;
  }

  /* ---------------- UI helpers ---------------- */
  function buildUI(opts) {
    opts = opts || {};
    const root = opts.mount || document.body;
    const pageBase = opts.pageBase || "../";   // where pages/ and data/ live
    const wrap = document.createElement("div");
    wrap.className = "pf2-search";
    wrap.innerHTML = ''
      + '<div class="pf2s-bar">'
      + '  <input type="search" id="pf2s-input" autocomplete="off"'
      + '         placeholder="搜索 (例: 黑暗视觉, anathema, demon)..." />'
      + '  <span id="pf2s-status"></span>'
      + '</div>'
      + '<div class="pf2s-results-host" id="pf2s-results-host"></div>';
    root.appendChild(wrap);
    const input  = wrap.querySelector("#pf2s-input");
    const status = wrap.querySelector("#pf2s-status");
    const host   = wrap.querySelector("#pf2s-results-host");

    // Active filter: when null all groups are visible; when set to a type
    // name (e.g. "spell"), only that group is shown. Toggled via chip clicks.
    let activeFilter = null;

    // Anchor the excerpt on the first query-term hit + <mark> highlight it.
    function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
    function highlightExcerpt(excerpt, q) {
      if (!excerpt) return "";
      var terms = (q || "").trim().toLowerCase().split(/\s+/).filter(function (t) { return t.length >= 1; });
      var lower = excerpt.toLowerCase();
      var first = -1;
      terms.forEach(function (t) { var i = lower.indexOf(t); if (i >= 0 && (first < 0 || i < first)) first = i; });
      var text = (first > 36) ? "…" + excerpt.slice(first - 12) : excerpt;
      var out = escapeHtml(text);
      terms.forEach(function (t) {
        if (!t) return;
        try {
          out = out.replace(new RegExp(escapeRegex(escapeHtml(t)), "gi"), function (m) { return "<mark>" + m + "</mark>"; });
        } catch (e) {}
      });
      return out;
    }

    function renderResults(rs) {
      if (!rs.length) {
        host.innerHTML = '<div class="pf2s-empty">未找到结果。试试更短的关键词，或检查拼写。</div>';
        return;
      }
      // Group by type
      const groups = Object.create(null);
      for (const r of rs) {
        const t = r.type || "other";
        (groups[t] = groups[t] || []).push(r);
      }
      const typeOrder = Object.keys(groups).sort(function (a, b) {
        const ai = (TYPE_INFO[a] || {}).order || 99;
        const bi = (TYPE_INFO[b] || {}).order || 99;
        return ai - bi;
      });

      const sum = '<div class="pf2s-summary">'
        + escapeHtml(String(rs.length)) + " 条结果，共 "
        + escapeHtml(String(typeOrder.length)) + " 类</div>";

      const chips = '<div class="pf2s-filters" role="tablist">'
        + '<button type="button" class="pf2s-chip kind-all" data-kind="__all">'
        + '全部 ' + escapeHtml(String(rs.length))
        + '</button>'
        + typeOrder.map(function (t) {
          const info = TYPE_INFO[t] || TYPE_INFO.other;
          return '<button type="button" class="pf2s-chip ' + info.className
            + '" data-kind="' + escapeAttr(t) + '">'
            + escapeHtml(info.label) + ' ' + escapeHtml(String(groups[t].length))
            + '</button>';
        }).join("") + '</div>';

      const groupHtml = typeOrder.map(function (t) {
        const info = TYPE_INFO[t] || TYPE_INFO.other;
        const items = groups[t].map(function (r) {
          // r.href already encodes the correct directory (pages/ data/ category/),
          // so prepend only pageBase. (Bug fix: previously re-added folder + "/" ->
          // pages/pages/X.html, 404ing every result; category results were unreachable.)
          const url = pageBase + r.href;
          const ex = r.excerpt
            ? '<div class="pf2s-ex">' + highlightExcerpt(r.excerpt, lastQ) + "</div>"
            : "";
          return ''
            + '<li class="pf2s-r">'
            + '<a class="pf2s-t" href="' + escapeAttr(url) + '">'
            +   '<span class="kind-badge ' + info.className + '">'
            +     escapeHtml(info.label)
            +   '</span>'
            +   '<span class="pf2s-title">' + escapeHtml(r.title) + '</span>'
            + '</a>'
            + ex
            + '</li>';
        }).join("");
        return '<section class="pf2s-group ' + info.className
          + '" data-group="' + escapeAttr(t) + '">'
          + '<h3 class="pf2s-group-h">'
          +   '<span class="kind-badge ' + info.className + '">'
          +     escapeHtml(info.label) + '</span>'
          +   ' <span class="pf2s-group-count">('
          +     escapeHtml(String(groups[t].length))
          +   ')</span>'
          + '</h3>'
          + '<ol class="pf2s-list">' + items + '</ol>'
          + '</section>';
      }).join("");

      host.innerHTML = sum + chips + groupHtml;
      applyFilter();

      // Wire up chips. Clicking a chip toggles its filter — click again to
      // restore "all". Filtering hides non-matching groups without re-querying.
      Array.prototype.forEach.call(
        host.querySelectorAll(".pf2s-chip"),
        function (b) {
          b.addEventListener("click", function () {
            const k = b.getAttribute("data-kind");
            if (k === "__all") {
              activeFilter = null;
            } else {
              activeFilter = (activeFilter === k) ? null : k;
            }
            applyFilter();
          });
        }
      );
    }

    function applyFilter() {
      const chips = host.querySelectorAll(".pf2s-chip");
      Array.prototype.forEach.call(chips, function (b) {
        const k = b.getAttribute("data-kind");
        const isActive = (activeFilter === null && k === "__all")
                      || (activeFilter !== null && k === activeFilter);
        b.classList.toggle("is-active", isActive);
      });
      const groups = host.querySelectorAll(".pf2s-group");
      Array.prototype.forEach.call(groups, function (g) {
        const k = g.getAttribute("data-group");
        g.style.display = (activeFilter === null || k === activeFilter) ? "" : "none";
      });
    }

    let debounce = null;
    let lastQ = "";
    input.addEventListener("input", function () {
      clearTimeout(debounce);
      const v = input.value;
      debounce = setTimeout(function () {
        if (v === lastQ) return;
        lastQ = v;
        if (!v.trim()) {
          host.innerHTML = "";
          status.textContent = "";
          activeFilter = null;
          return;
        }
        status.textContent = "搜索中…";
        const t0 = performance.now();
        query(v, { limit: 50 }).then(function (rs) {
          const dt = (performance.now() - t0).toFixed(1);
          status.textContent = rs.length + " 条结果 · " + dt + " ms";
          // Reset filter for each new query so chip state never lies.
          activeFilter = null;
          renderResults(rs);
        }).catch(function (e) {
          status.textContent = "错误: " + e.message;
          host.innerHTML = "";
        });
      }, 80);
    });
    return { input: input, host: host, status: status };
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }
  function escapeAttr(s) { return escapeHtml(s); }

  /* ---------------- export ---------------- */
  W.PF2Search.init = init;
  W.PF2Search.query = query;
  W.PF2Search.buildUI = buildUI;
  W.PF2Search._parseQuery = parseQuery;
  W.PF2Search._bigramBucket = bigramBucket;
})();
