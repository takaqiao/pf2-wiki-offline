// acl_probe.mjs — runtime ACL / IPC probe for the real Tauri WebView2.
//
// WHY THIS EXISTS:
//   The wiki is served over http://127.0.0.1:<random-port> by tiny_http and the
//   webview navigates there, so its IPC origin is REMOTE (not the tauri:// Local
//   origin). Tauri's ACL grants are origin-scoped: a capability with only
//   `local: true` grants NOTHING to a remote origin (Origin::matches returns
//   false for (Remote, Local)) and every invoke is rejected with
//   "Command X not allowed by ACL". The capability MUST declare
//   `remote.urls: ["http://127.0.0.1:*", "http://localhost:*"]` (port is random,
//   so the port component must be the `*` wildcard).
//
//   Static config (permissions/*.toml, gen/schemas, capabilities.json) can look
//   100% correct yet still fail at runtime on this origin mismatch. The ONLY way
//   to confirm the real behaviour without a user round-trip is to drive the
//   actual WebView2 over CDP. Pure built-in Node (fetch + WebSocket), no deps.
//
// USAGE:
//   1. Launch the portable exe with remote debugging + isolated user-data:
//        $env:WEBVIEW2_USER_DATA_FOLDER       = "$env:TEMP\pf2_acl_udf"
//        $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
//        Start-Process .\pf2-wiki.exe -WorkingDirectory <portable-folder>
//   2. node src-tauri/diagnostics/acl_probe.mjs
//   3. Look at invokeError: "...not allowed by ACL" => still broken;
//      invokeResult: "RESOLVED ..." => fixed. Kill the instance + remove the UDF.
//
// NOTE: open_external in this probe opens a real browser tab to example.com when
// the ACL passes — that tab opening IS the success signal.

const PORT = 9222;
const DEADLINE = Date.now() + 25000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findWikiTarget() {
  while (Date.now() < DEADLINE) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find(
        (t) =>
          t.type === 'page' &&
          typeof t.url === 'string' &&
          /^http:\/\/127\.0\.0\.1:\d+\//.test(t.url) &&
          t.url.indexOf(`:${PORT}/`) === -1
      );
      if (page && page.webSocketDebuggerUrl) return page;
    } catch { /* port not up yet */ }
    await sleep(400);
  }
  return null;
}

const EXPR = `(async () => {
  const out = { href: location.href, readyState: document.readyState };
  out.hasTAURI = typeof window.__TAURI__;
  out.tauriKeys = window.__TAURI__ ? Object.keys(window.__TAURI__) : null;
  out.extLinksLoaded = !!document.querySelector('script[src*="external_links.js"]');
  let inv = null, src = null;
  if (window.__TAURI__?.core?.invoke) { inv = window.__TAURI__.core.invoke.bind(window.__TAURI__.core); src='__TAURI__.core.invoke'; }
  else if (window.__TAURI__?.invoke) { inv = window.__TAURI__.invoke.bind(window.__TAURI__); src='__TAURI__.invoke'; }
  else if (window.__TAURI_INTERNALS__?.invoke) { inv = window.__TAURI_INTERNALS__.invoke.bind(window.__TAURI_INTERNALS__); src='__TAURI_INTERNALS__.invoke'; }
  out.invokeFound = !!inv; out.invokeSrc = src;
  if (inv) {
    try { await inv('open_external', { url: 'https://example.com/__pf2_diag__' }); out.invokeResult = 'RESOLVED — open_external succeeded'; }
    catch (e) { out.invokeError = String(e && e.message ? e.message : e); }
    try { await inv('apply_incremental_update', { patches: [] }); out.updateApply = 'RESOLVED(unexpected)'; }
    catch (e) { out.updateApply = String(e && e.message ? e.message : e); } // "no patches to apply" = ACL passed
    try { const un = await window.__TAURI__.event.listen('update-available', () => {}); un(); out.eventListen = 'OK'; }
    catch (e) { out.eventListen = 'ERR: ' + String(e); }
  }
  return JSON.stringify(out);
})()`;

function cdp(ws, method, params) {
  return new Promise((resolve, reject) => {
    const id = (cdp._id = (cdp._id || 0) + 1);
    const onMsg = (event) => {
      let m; try { m = JSON.parse(event.data); } catch { return; }
      if (m.id === id) { ws.removeEventListener('message', onMsg); resolve(m); }
    };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => reject(new Error(`CDP timeout: ${method}`)), 15000);
  });
}

(async () => {
  const target = await findWikiTarget();
  if (!target) { console.log(JSON.stringify({ error: 'no wiki target on CDP — exe not up or no --remote-debugging-port' })); process.exit(2); }
  console.log('TARGET_URL=' + target.url);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  await cdp(ws, 'Runtime.enable', {});
  const res = await cdp(ws, 'Runtime.evaluate', { expression: EXPR, awaitPromise: true, returnByValue: true });
  console.log('PROBE=' + (res.result?.result?.value ?? JSON.stringify(res.result || res)));
  ws.close(); process.exit(0);
})().catch((e) => { console.log('FATAL=' + (e && e.stack || e)); process.exit(1); });
