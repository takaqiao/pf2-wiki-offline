/* ============================================================
   bookmark.js — Phase F+ : Bookmarks & Recently Visited
   --------------------------------------------------------------
   Adds a ☆/★ toggle button into .topnav-tools on every page, and
   injects two <details> groups (★ 收藏夹 / ⌚ 最近) into the
   .wiki-sidebar (when present).

   Storage:
     localStorage["pf2_bookmarks"]  = [{path, title, ts}, ...]
     localStorage["pf2_recent"]     = [{path, title, ts}, ...]  (max 20)

   `path` is a site-relative href rooted at the wiki root (e.g.
   "pages/战士.html" or "browse-spells.html") so links work no
   matter which depth the consumer page lives at.

   No external deps. Vanilla JS, IIFE, idempotent.
   ============================================================ */
(function () {
  "use strict";

  var BM_KEY = "pf2_bookmarks";
  var RC_KEY = "pf2_recent";
  var RC_MAX = 20;

  // ---------- storage helpers ----------
  function load(key) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return [];
      var arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) { return []; }
  }
  function save(key, arr) {
    try { localStorage.setItem(key, JSON.stringify(arr)); }
    catch (e) { /* quota / disabled — ignore */ }
  }

  // ---------- path normalization ----------
  // Compute a site-relative key for the current page, rooted at the
  // wiki root (the directory that contains index.html). Strips query
  // and hash, so two visits to the same page collapse into one entry.
  function computeSitePath() {
    var loc = window.location;
    // file:// or http://host/whatever/_wiki_full_v2/pages/战士.html
    var p = loc.pathname || "";
    try { p = decodeURIComponent(p); } catch (e) {}
    // Strip trailing slash → index
    if (p.endsWith("/")) p += "index.html";
    // Drop everything before "_wiki_full_v2/" if present (so paths are
    // portable across deployments where the wiki may be mounted under
    // different prefixes).
    var anchorIdx = p.lastIndexOf("/_wiki_full_v2/");
    if (anchorIdx >= 0) {
      p = p.substring(anchorIdx + "/_wiki_full_v2/".length);
    } else {
      // No anchor: take last 1-2 segments. We assume the wiki root has
      // index.html + asset/ + pages/ etc., so the page lives at most
      // 1 dir deep below the wiki root.
      var segs = p.split("/").filter(Boolean);
      if (segs.length === 0) return "index.html";
      // Heuristic: if penultimate looks like a known subdir, keep both.
      var known = {pages:1, data:1, category:1, project:1, classes:1, source:1, index:1};
      if (segs.length >= 2 && known[segs[segs.length - 2]]) {
        p = segs[segs.length - 2] + "/" + segs[segs.length - 1];
      } else {
        p = segs[segs.length - 1];
      }
    }
    return p;
  }

  // Compute prefix from current document to the wiki root (so we can
  // emit working <a href> values to bookmarks). Pages under /pages/foo
  // need "../"; pages at root need "".
  function computeRootPrefix() {
    // Look at document.querySelector('a.topnav-brand') which the build
    // step authors as either "index.html" or "../index.html".
    var brand = document.querySelector("a.topnav-brand, .sb-home");
    if (brand) {
      var h = brand.getAttribute("href") || "";
      var idx = h.lastIndexOf("index.html");
      if (idx >= 0) return h.substring(0, idx);
    }
    // Fallback: count path depth.
    var p = window.location.pathname || "";
    var anchorIdx = p.lastIndexOf("/_wiki_full_v2/");
    if (anchorIdx >= 0) {
      var rest = p.substring(anchorIdx + "/_wiki_full_v2/".length);
      var depth = rest.split("/").length - 1;
      return depth > 0 ? new Array(depth + 1).join("../") : "";
    }
    return "";
  }

  // ---------- title extraction ----------
  function computeTitle() {
    // Prefer h1.page-head or <h1>, fall back to <title>.
    var h1 = document.querySelector("header.page-head h1") || document.querySelector("h1");
    if (h1) {
      var t = (h1.textContent || "").trim();
      if (t) return t;
    }
    var dt = (document.title || "").trim();
    // Strip " — PF2 离线百科" suffix.
    var dash = dt.indexOf(" — ");
    if (dash > 0) dt = dt.substring(0, dash);
    return dt || "(无标题)";
  }

  // ---------- record visit ----------
  function recordRecent(path, title) {
    if (!path || /^index\.html$/i.test(path)) return; // skip landing page
    var rc = load(RC_KEY);
    // Remove existing entry for same path
    rc = rc.filter(function (e) { return e && e.path !== path; });
    rc.unshift({ path: path, title: title, ts: Date.now() });
    if (rc.length > RC_MAX) rc = rc.slice(0, RC_MAX);
    save(RC_KEY, rc);
  }

  // ---------- bookmark ops ----------
  function isBookmarked(path) {
    var bm = load(BM_KEY);
    for (var i = 0; i < bm.length; i++) {
      if (bm[i] && bm[i].path === path) return true;
    }
    return false;
  }
  function toggleBookmark(path, title) {
    var bm = load(BM_KEY);
    var idx = -1;
    for (var i = 0; i < bm.length; i++) {
      if (bm[i] && bm[i].path === path) { idx = i; break; }
    }
    if (idx >= 0) {
      bm.splice(idx, 1);
      save(BM_KEY, bm);
      return false;
    }
    bm.unshift({ path: path, title: title, ts: Date.now() });
    save(BM_KEY, bm);
    return true;
  }

  // ---------- UI: topnav star button ----------
  function ensureStyles() {
    if (document.getElementById("pf2-bookmark-style")) return;
    var s = document.createElement("style");
    s.id = "pf2-bookmark-style";
    s.textContent = [
      ".topnav-bookmark{",
      "  display:inline-flex;align-items:center;justify-content:center;",
      "  width:34px;height:30px;margin-left:4px;padding:0;",
      "  background:transparent;color:var(--accent-on,#fff);",
      "  border:1px solid rgba(255,255,255,0.25);border-radius:4px;",
      "  font-size:18px;line-height:1;cursor:pointer;",
      "  transition:background .15s,color .15s,border-color .15s;",
      "}",
      ".topnav-bookmark:hover{background:rgba(255,255,255,0.18);}",
      ".topnav-bookmark.is-on{color:#ffd766;border-color:#ffd766;}",
      ".topnav-bookmark.is-on:hover{background:rgba(255,215,102,0.15);}",
      // Sidebar groups
      "nav.wiki-sidebar details.sb-group.sb-bookmarks > summary,",
      "nav.wiki-sidebar details.sb-group.sb-recent > summary{",
      "  color:var(--accent,#7a1f00);",
      "}",
      "nav.wiki-sidebar details.sb-group ul.sb-bm-list,",
      "nav.wiki-sidebar details.sb-group ul.sb-rc-list{",
      "  padding-left:8px;",
      "}",
      "nav.wiki-sidebar details.sb-group .sb-bm-empty{",
      "  color:var(--fg-mute,#888);font-size:12px;font-style:italic;",
      "  padding:4px 0;",
      "}",
      "nav.wiki-sidebar details.sb-group li.sb-bm-item{",
      "  display:flex;align-items:flex-start;gap:4px;padding:2px 0;",
      "  font-size:12.5px;line-height:1.35;",
      "}",
      "nav.wiki-sidebar details.sb-group li.sb-bm-item a{",
      "  flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;",
      "  white-space:nowrap;",
      "}",
      "nav.wiki-sidebar details.sb-group li.sb-bm-item .sb-bm-remove{",
      "  flex:0 0 auto;background:transparent;border:0;cursor:pointer;",
      "  color:var(--fg-mute,#999);font-size:11px;padding:0 4px;",
      "}",
      "nav.wiki-sidebar details.sb-group li.sb-bm-item .sb-bm-remove:hover{",
      "  color:#c33;",
      "}",
      ""
    ].join("\n");
    document.head.appendChild(s);
  }

  function ensureStarButton(path, title) {
    var tools = document.querySelector(".topnav-tools");
    if (!tools) return null;
    if (tools.querySelector(".topnav-bookmark")) return tools.querySelector(".topnav-bookmark");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "topnav-bookmark";
    btn.setAttribute("aria-label", "收藏本页");
    btn.setAttribute("title", "收藏本页");
    btn.textContent = "☆"; // ☆
    // Insert *before* the theme toggle if present, else append.
    var theme = tools.querySelector(".topnav-theme");
    if (theme) tools.insertBefore(btn, theme);
    else tools.appendChild(btn);
    refreshStarButton(btn, path);
    btn.addEventListener("click", function () {
      var nowOn = toggleBookmark(path, title);
      refreshStarButton(btn, path);
      // Re-render sidebar bookmarks list
      renderSidebar(path);
      // Quick feedback
      btn.setAttribute("title", nowOn ? "已收藏（点击取消）" : "收藏本页");
    });
    return btn;
  }
  function refreshStarButton(btn, path) {
    if (!btn) return;
    if (isBookmarked(path)) {
      btn.textContent = "★"; // ★
      btn.classList.add("is-on");
      btn.setAttribute("aria-pressed", "true");
    } else {
      btn.textContent = "☆"; // ☆
      btn.classList.remove("is-on");
      btn.setAttribute("aria-pressed", "false");
    }
  }

  // ---------- UI: sidebar groups ----------
  function renderList(items, listClass, emptyMsg, rootPrefix, currentPath, withRemove) {
    if (!items || !items.length) {
      var em = document.createElement("div");
      em.className = "sb-bm-empty";
      em.textContent = emptyMsg;
      return em;
    }
    var ul = document.createElement("ul");
    ul.className = listClass;
    ul.style.listStyle = "none";
    ul.style.margin = "4px 0 8px";
    items.forEach(function (e) {
      if (!e || !e.path) return;
      var li = document.createElement("li");
      li.className = "sb-bm-item";
      var a = document.createElement("a");
      a.href = rootPrefix + e.path;
      a.textContent = e.title || e.path;
      a.title = e.title || e.path;
      if (e.path === currentPath) {
        a.style.fontWeight = "600";
      }
      li.appendChild(a);
      if (withRemove) {
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "sb-bm-remove";
        rm.textContent = "×"; // ×
        rm.setAttribute("aria-label", "移除收藏");
        rm.title = "移除";
        rm.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          var bm = load(BM_KEY).filter(function (x) { return x && x.path !== e.path; });
          save(BM_KEY, bm);
          renderSidebar(currentPath);
          var topBtn = document.querySelector(".topnav-bookmark");
          if (topBtn) refreshStarButton(topBtn, currentPath);
        });
        li.appendChild(rm);
      }
      ul.appendChild(li);
    });
    return ul;
  }

  function buildOrUpdateSidebarGroup(sidebar, cls, summaryText, replaceWith) {
    var details = sidebar.querySelector("details.sb-group." + cls);
    if (!details) {
      details = document.createElement("details");
      details.className = "sb-group " + cls;
      var sum = document.createElement("summary");
      sum.textContent = summaryText;
      details.appendChild(sum);
      // Insert as the first details after the search form so the user
      // sees these groups before the canonical nav groups.
      var anchor = sidebar.querySelector("form.sb-search") || sidebar.querySelector(".sb-home");
      if (anchor && anchor.nextSibling) {
        sidebar.insertBefore(details, anchor.nextSibling);
      } else {
        sidebar.appendChild(details);
      }
    }
    // Remove all children after the summary
    var sumEl = details.querySelector("summary");
    while (details.lastChild && details.lastChild !== sumEl) {
      details.removeChild(details.lastChild);
    }
    details.appendChild(replaceWith);
    return details;
  }

  function renderSidebar(currentPath) {
    var sidebar = document.querySelector("nav.wiki-sidebar");
    if (!sidebar) return;
    var rootPrefix = computeRootPrefix();
    var bm = load(BM_KEY);
    var rc = load(RC_KEY);
    var bmList = renderList(bm, "sb-bm-list", "（暂无收藏，点击页面右上 ☆ 添加）", rootPrefix, currentPath, true);
    var rcList = renderList(rc, "sb-rc-list", "（暂无访问记录）", rootPrefix, currentPath, false);
    // Recent group goes after bookmarks; insert bookmarks first so
    // insertion-as-first puts ★ above ⌚.
    buildOrUpdateSidebarGroup(sidebar, "sb-recent", "⌚ 最近", rcList);
    buildOrUpdateSidebarGroup(sidebar, "sb-bookmarks", "★ 收藏夹", bmList);
    // Open bookmarks group if user has any.
    var bmDetails = sidebar.querySelector("details.sb-group.sb-bookmarks");
    if (bmDetails && bm.length > 0 && !bmDetails.hasAttribute("data-pf2-opened")) {
      bmDetails.setAttribute("open", "");
      bmDetails.setAttribute("data-pf2-opened", "1");
    }
  }

  // ---------- bootstrap ----------
  function init() {
    ensureStyles();
    var path = computeSitePath();
    var title = computeTitle();
    // Record visit (after a microtask so we don't pollute storage on hot
    // reloads of the same page during dev — but Date.now changes anyway).
    recordRecent(path, title);
    ensureStarButton(path, title);
    renderSidebar(path);
    // Expose for debugging
    window.PF2Bookmark = {
      bookmarks: function () { return load(BM_KEY); },
      recent: function () { return load(RC_KEY); },
      clear: function () { save(BM_KEY, []); save(RC_KEY, []); renderSidebar(path); var b = document.querySelector(".topnav-bookmark"); if (b) refreshStarButton(b, path); }
    };
  }

  if (document.readyState !== "loading") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
