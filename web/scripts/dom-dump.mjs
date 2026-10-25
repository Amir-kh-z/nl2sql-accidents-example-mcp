// P10: real-time DOM dump via CDP — the P6 recipe (--headless=new --virtual-time-budget --dump-dom) dumps at
// a fixed early point and never waits for a lazy-chunk SPA's in-flight fetch (the identical byte-length dump
// is the tell). This harness navigates, waits WALL-CLOCK milliseconds, then evaluates the live DOM.
// Usage: node dom-dump.mjs <url> <waitMs> <outFile>   (Node >= 22: global fetch + WebSocket)
import { spawn } from "node:child_process";
import { writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, waitMsArg, out] = process.argv.slice(2);
if (!url || !out) { console.error("usage: node dom-dump.mjs <url> <waitMs> <outFile>"); process.exit(2); }
const waitMs = Number(waitMsArg) || 8000;
const port = 9223;
const edge = process.env.EDGE_EXE
  || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const profile = mkdtempSync(join(tmpdir(), "dom-dump-"));
const proc = spawn(edge, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws;
let code = 1;
try {
  let page;
  for (let i = 0; i < 60 && !page; i += 1) {
    await sleep(250);
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      page = targets.find((t) => t.type === "page");
    } catch { /* not up yet */ }
  }
  if (!page) throw new Error("no CDP page target after 15s");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws failed")); });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  const send = (method, params) => new Promise((res) => {
    id += 1; pending.set(id, res); ws.send(JSON.stringify({ id, method, params: params || {} }));
  });
  await send("Page.enable");
  await send("Page.navigate", { url });
  await sleep(waitMs);
  const r = await send("Runtime.evaluate", {
    expression: "document.documentElement.outerHTML", returnByValue: true,
  });
  const html = (r.result && r.result.result && r.result.result.value) || "";
  writeFileSync(out, html, "utf8");
  console.log(`dom-dump: ${html.length} chars -> ${out}`);
  code = html.length > 0 ? 0 : 1;
} catch (e) {
  console.error(`dom-dump failed: ${e.message}`);
} finally {
  try { if (ws) ws.close(); } catch { /* closed */ }
  try { proc.kill(); } catch { /* gone */ }
}
process.exit(code);
