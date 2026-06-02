/* PF2 offline wiki — theme toggle
 * Reads localStorage.theme ("dark" | "light"), applies class to <body>.
 * Exposes window.toggleTheme() for the header button.
 * Vanilla JS, no deps. Safe to include before or after the toggle button.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var DARK = "dark";
  var LIGHT = "light";

  function getStored() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }
  function setStored(v) {
    try { localStorage.setItem(STORAGE_KEY, v); } catch (e) { /* ignore */ }
  }
  function prefersDark() {
    return window.matchMedia &&
           window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function apply(theme) {
    // Sync BOTH <html> (set pre-paint by the inline head script, kills FOUC)
    // and <body> (the ~189 body.dark rules in _v2_compat.css match this).
    var html = document.documentElement;
    var on = theme === DARK;
    html.classList.toggle(DARK, on);
    html.classList.toggle(LIGHT, !on);
    var body = document.body;
    if (!body) return;
    if (theme === DARK) {
      body.classList.add(DARK);
      body.classList.remove(LIGHT);
    } else {
      body.classList.remove(DARK);
      body.classList.add(LIGHT);
    }
    // Update any toggle buttons' visible glyph
    var btns = document.querySelectorAll(".theme-toggle, [data-theme-toggle], .topnav-theme, .sb-theme, .topnav-fallback-theme");
    for (var i = 0; i < btns.length; i++) {
      var b = btns[i];
      // Only swap text if button has just one of these glyphs
      var t = (b.textContent || "").trim();
      if (t === "\u{1F319}" || t === "☀" || t === "☀️" ||
          t === "\u{1F31E}" || t === "Dark" || t === "Light") {
        b.textContent = theme === DARK ? "☀️" : "\u{1F319}";
      }
      b.setAttribute("aria-pressed", theme === DARK ? "true" : "false");
      b.setAttribute("title", theme === DARK ? "切换到亮色主题" : "切换到暗色主题");
    }
  }

  function resolveInitial() {
    var stored = getStored();
    if (stored === DARK || stored === LIGHT) return stored;
    // No explicit choice — fall back to system; CSS @media handles it,
    // but we still set a class so other JS can read body.classList.
    return prefersDark() ? DARK : LIGHT;
  }

  function injectSkipLink() {
    // a11y: prepend a "Skip to main content" link as the first focusable
    // element. Hidden by P11 .skip-link CSS until keyboard focus reveals it.
    // Idempotent.
    if (!document.body || document.querySelector("a.skip-link")) return;
    var main = document.querySelector("main");
    if (!main) return;
    // Ensure target has id
    if (!main.id) main.id = "main-content";
    var a = document.createElement("a");
    a.className = "skip-link";
    a.href = "#" + main.id;
    a.textContent = "跳到主要内容";
    document.body.insertBefore(a, document.body.firstChild);
  }

  function init() {
    apply(resolveInitial());
    injectSkipLink();
  }

  // Shared toast primitive (aria-live). window.pf2Toast(msg, {undo, duration}).
  // Used by bookmark/copy-link/etc for humane action feedback. CSS in _components.css.
  window.pf2Toast = function (msg, opts) {
    opts = opts || {};
    var host = document.getElementById("pf2-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "pf2-toast-host";
      host.setAttribute("aria-live", "polite");
      (document.body || document.documentElement).appendChild(host);
    }
    var t = document.createElement("div");
    t.className = "pf2-toast";
    var span = document.createElement("span");
    span.textContent = msg;
    t.appendChild(span);
    if (typeof opts.undo === "function") {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = opts.undoLabel || "撤销";
      b.addEventListener("click", function () { try { opts.undo(); } catch (e) {} remove(); });
      t.appendChild(b);
    }
    host.appendChild(t);
    var timer = setTimeout(remove, opts.duration || 3200);
    function remove() { clearTimeout(timer); if (t.parentNode) t.parentNode.removeChild(t); }
    return remove;
  };

  window.toggleTheme = function () {
    // Read current from <html> so it works even before <body> is ready.
    var current = document.documentElement.classList.contains(DARK) ? DARK : LIGHT;
    var next = current === DARK ? LIGHT : DARK;
    setStored(next);
    apply(next);
  };

  // Apply ASAP to minimize flash; run again on DOMContentLoaded for safety.
  if (document.body) {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }

  // React to OS-level changes only if user has not chosen explicitly
  if (window.matchMedia) {
    var mq = window.matchMedia("(prefers-color-scheme: dark)");
    var listener = function (e) {
      if (getStored()) return; // user has chosen explicitly
      apply(e.matches ? DARK : LIGHT);
    };
    if (mq.addEventListener) mq.addEventListener("change", listener);
    else if (mq.addListener) mq.addListener(listener);
  }
})();
