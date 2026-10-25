// The single door to the app. Three failure layers — HTTP status, `ok:false` (the CALL failed: no such module,
// missing input, the plugin raised), and `kind:"error"` (the plugin's own answer) — the first two throw; the third
// is returned as an envelope so the answer anatomy can render it as an error box next to the form.
// the module id the core registers us under — MUST equal MODULE.name in __init__.py and the
// nl2sql.modules entry-point name (renamed 2026-09-09; every runAction posts this string)
const MODULE = "roadsafety";

async function handle(r) {
  if (r.ok) return r.json();
  let message = `${r.status} ${r.statusText}`;
  try {
    const body = await r.json();
    message = body?.detail?.message || (typeof body?.detail === "string" ? body.detail : message);
    try {                                   // the app sometimes JSON-encodes the message itself ("\"no connection …\"")
      const inner = JSON.parse(message);
      if (typeof inner === "string") message = inner;
    } catch { /* plain text */ }
  } catch {
    /* not JSON */
  }
  throw new Error(message);
}

export async function listModules() {
  return fetch("/api/modules").then(handle);
}

export async function listConnections() {
  return fetch("/api/connections").then(handle);
}

// P13: one page-wide busy signal, REF-COUNTED — every runAction increments on start and decrements in
// a finally, so overlapping runs (compare rows, the map fetch, a slow training next to a quick trend)
// can never clear the chip early. A boolean would: the first finisher would blank it under the second.
let busyCount = 0;
const busyWatchers = new Set();

function bumpBusy(delta) {
  busyCount = Math.max(0, busyCount + delta);
  busyWatchers.forEach((cb) => {
    try { cb(busyCount); } catch { /* one broken subscriber never blocks the rest */ }
  });
}

/** Subscribe to the in-flight run count (called immediately with the current value); returns unsubscribe. */
export function subscribeBusy(cb) {
  busyWatchers.add(cb);
  cb(busyCount);
  return () => { busyWatchers.delete(cb); };
}

/** Run one action. Returns the envelope {ok, kind, data, title, note}; throws on HTTP failure or ok:false. */
export async function runAction(action, db, inputs) {
  bumpBusy(1);
  try {
    const res = await fetch("/api/modules/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ module: MODULE, action, db, inputs: inputs || {} }),
    }).then(handle);
    if (!res.ok) throw new Error(res.hint ? `${res.error}\n${res.hint}` : res.error || "the call failed");
    return res;
  } finally {
    bumpBusy(-1);
  }
}

/** The db name the sidebar link appends at click time; a stale tab keeps its old db (say so in the header). */
export function dbFromUrl() {
  return new URLSearchParams(window.location.search).get("db") || "";
}

export function tabFromUrl() {
  return new URLSearchParams(window.location.search).get("tab") || "";
}

export function setUrlParam(name, value) {
  const url = new URL(window.location.href);
  if (value) url.searchParams.set(name, value);
  else url.searchParams.delete(name);
  window.history.replaceState(null, "", url.toString());
}
