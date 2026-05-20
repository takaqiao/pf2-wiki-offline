// updater_logic_test.mjs — exercises the REAL assets/updater_ui.js in a mocked
// DOM/fetch environment to verify the patches.json-driven detection, the 6h
// network throttle + cache, banner construction, and the apply payload.
// Pure built-in Node. Run: node src-tauri/diagnostics/updater_logic_test.mjs
import { readFileSync } from 'node:fs';

const SRC = 'C:/Users/Taka/Desktop/fvtt/_wiki_full_v2/assets/updater_ui.js';
const code = readFileSync(SRC, 'utf8');

const PATCHES = {
  latest: 'v0.3.22',
  chain: {
    'v0.3.20': { to: 'v0.3.21', url: 'u20', sha256: 's20', size_mb: 5.17 },
    'v0.3.21': { to: 'v0.3.22', url: 'u21', sha256: 's21', size_mb: 5.2 },
  },
};

let pass = 0, fail = 0;
function ok(name, cond) { (cond ? (pass++, console.log('  PASS ' + name)) : (fail++, console.log('  FAIL ' + name))); }

// Build a fresh sandbox per scenario and run updater_ui.js inside it.
function run({ currentVersion, patches, fetchPatchesFails = false, seedLocalStorage = {} }) {
  const store = { ...seedLocalStorage };
  const localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
  };
  const invokeCalls = [];
  const banner = { created: false, html: '', handlers: {} };
  let fetchPatchesCount = 0;

  const elements = {};
  function makeEl() {
    return {
      id: '', style: {}, _html: '',
      set innerHTML(v) { this._html = v; banner.html = v; },
      get innerHTML() { return this._html; },
      appendChild() {}, remove() {},
      addEventListener(ev, fn) { /* banner div itself: capture click handlers via getElementById path */ },
      set textContent(v) {}, get textContent() { return ''; }, disabled: false,
    };
  }
  const doc = {
    readyState: 'complete',
    querySelector: () => null,
    getElementById: (id) => {
      if (id === 'pf2-updater-banner') return banner.created ? elements.banner : null;
      return elements[id] || null;
    },
    createElement: () => { const e = makeEl(); elements.banner = e; return e; },
    body: { appendChild: () => { banner.created = true; wireButtons(); } },
    addEventListener: () => {},
  };
  // After innerHTML is set, expose button elements that record their click handler.
  function wireButtons() {
    ['pf2-updater-patch', 'pf2-updater-full', 'pf2-updater-page', 'pf2-updater-dismiss', 'pf2-updater-msg'].forEach((id) => {
      elements[id] = {
        style: {}, disabled: false, _t: '', set textContent(v) { this._t = v; }, get textContent() { return this._t; },
        set innerHTML(v) {}, get innerHTML() { return ''; },
        addEventListener: (ev, fn) => { banner.handlers[id] = fn; },
      };
    });
  }

  const win = {
    __TAURI__: { core: { invoke: (cmd, args) => { invokeCalls.push({ cmd, args }); return Promise.resolve(); } } },
    open: () => {},
  };

  const fetch = (url) => {
    if (url.indexOf('_app_version.json') !== -1) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: currentVersion }) });
    }
    if (url.indexOf('patches.json') !== -1) {
      fetchPatchesCount++;
      if (fetchPatchesFails) return Promise.resolve({ ok: false, json: () => Promise.resolve(null) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve(patches) });
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve(null) });
  };

  // setTimeout fires immediately so check() runs synchronously-ish.
  const fakeSetTimeout = (fn) => { fn(); return 0; };

  const sandbox = { window: win, document: doc, localStorage, fetch, setTimeout: fakeSetTimeout, Date };
  const fn = new Function('window', 'document', 'localStorage', 'fetch', 'setTimeout', 'Date', code);
  fn(win, doc, localStorage, fetch, fakeSetTimeout, Date);

  return { banner, invokeCalls, store, getFetchCount: () => fetchPatchesCount };
}

// Helper to flush microtasks (promise chains in check()).
const flush = () => new Promise((r) => setImmediate(r));

(async () => {
  console.log('Scenario 1: update available (current v0.3.21, latest v0.3.22)');
  {
    const r = run({ currentVersion: 'v0.3.21', patches: PATCHES });
    await flush(); await flush(); await flush(); await flush();
    ok('banner shown', r.banner.created);
    ok('banner mentions v0.3.22', r.banner.html.includes('v0.3.22'));
    ok('one-click patch button present', r.banner.html.includes('一键自动更新'));
    ok('chain is 1 step (v0.3.21->v0.3.22)', r.banner.html.includes('一键自动更新 (') && !r.banner.html.includes('个补丁'));
    // click the patch button → should invoke apply_incremental_update with [{url:u21,sha256:s21}]
    if (r.banner.handlers['pf2-updater-patch']) r.banner.handlers['pf2-updater-patch']();
    await flush();
    const call = r.invokeCalls.find((c) => c.cmd === 'apply_incremental_update');
    ok('apply_incremental_update invoked', !!call);
    ok('payload = single step u21/s21', call && JSON.stringify(call.args.patches) === JSON.stringify([{ url: 'u21', sha256: 's21' }]));
    ok('patches.json cached in localStorage', !!r.store['pf2_updater_patches_cache']);
    ok('throttle timestamp set', !!r.store['pf2_updater_last_check']);
  }

  console.log('Scenario 2: up to date (current == latest v0.3.22)');
  {
    const r = run({ currentVersion: 'v0.3.22', patches: PATCHES });
    await flush(); await flush(); await flush();
    ok('no banner', !r.banner.created);
  }

  console.log('Scenario 3: multi-step chain (current v0.3.20 → latest v0.3.22)');
  {
    const r = run({ currentVersion: 'v0.3.20', patches: PATCHES });
    await flush(); await flush(); await flush();
    ok('banner shown', r.banner.created);
    ok('shows "2 个补丁"', r.banner.html.includes('2 个补丁'));
    if (r.banner.handlers['pf2-updater-patch']) r.banner.handlers['pf2-updater-patch']();
    await flush();
    const call = r.invokeCalls.find((c) => c.cmd === 'apply_incremental_update');
    ok('payload = 2 steps u20,u21', call && JSON.stringify(call.args.patches) === JSON.stringify([{ url: 'u20', sha256: 's20' }, { url: 'u21', sha256: 's21' }]));
  }

  console.log('Scenario 4: throttle — fresh cache, no network fetch');
  {
    const seed = {
      pf2_updater_last_check: String(Date.now() - 60 * 1000), // checked 1 min ago
      pf2_updater_patches_cache: JSON.stringify(PATCHES),
    };
    const r = run({ currentVersion: 'v0.3.21', patches: PATCHES, seedLocalStorage: seed });
    await flush(); await flush(); await flush();
    ok('no network fetch (used cache)', r.getFetchCount() === 0);
    ok('banner still shown from cache', r.banner.created);
  }

  console.log('Scenario 5: network fails but stale cache exists → falls back');
  {
    const seed = {
      pf2_updater_last_check: String(Date.now() - 7 * 60 * 60 * 1000), // 7h ago = throttle expired
      pf2_updater_patches_cache: JSON.stringify(PATCHES),
    };
    const r = run({ currentVersion: 'v0.3.21', patches: PATCHES, fetchPatchesFails: true, seedLocalStorage: seed });
    await flush(); await flush(); await flush();
    ok('attempted network (throttle expired)', r.getFetchCount() === 1);
    ok('banner shown from cache fallback', r.banner.created);
  }

  console.log('\nUpdater logic: ' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail ? 1 : 0);
})();
