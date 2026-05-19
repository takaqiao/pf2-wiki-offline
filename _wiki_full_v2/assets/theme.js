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
    var btns = document.querySelectorAll(".theme-toggle, [data-theme-toggle]");
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

  window.toggleTheme = function () {
    var current = document.body.classList.contains(DARK) ? DARK : LIGHT;
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
