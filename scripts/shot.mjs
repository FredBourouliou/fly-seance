// Screenshot a page of web/ in a real browser, with WebGL, without opening a port.
//
//   node scripts/shot.mjs fly/test.html web/fly/renders/web_rest.png
//   node scripts/shot.mjs fly/test.html out.png --js "window.fly?.setDrive({feed:1, groom:0})" --wait 2500
//   node scripts/shot.mjs index.html out.png --size 390x844 --browser webkit
//
// Options: --js <code> (run after load, may be async), --wait <ms> (default 2000),
// --size WxH (default 1280x800), --browser chromium|webkit (default chromium),
// --fps (also report frame timing over 2 s). Console errors and page errors are
// printed; the exit code is 1 if there were any.

import { readFile } from "node:fs/promises";
import { dirname, extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PW = "/opt/homebrew/lib/node_modules/@playwright/test/index.mjs";
const { chromium, webkit } = await import(PW);

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..", "web");
const ORIGIN = "http://fly.local";
const TYPES = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
  ".bin": "application/octet-stream", ".png": "image/png", ".jpg": "image/jpeg",
  ".svg": "image/svg+xml", ".woff2": "font/woff2", ".ktx2": "image/ktx2", ".hdr": "application/octet-stream",
};

const args = process.argv.slice(2);
const [path, out] = args;
if (!path || !out) {
  console.error("usage: node scripts/shot.mjs <path under web/> <out.png> [--js code] [--wait ms] [--size WxH] [--browser chromium|webkit] [--fps]");
  process.exit(2);
}
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const [width, height] = opt("--size", "1280x800").split("x").map(Number);
const engine = opt("--browser", "chromium");

const browser = engine === "webkit"
  ? await webkit.launch()
  : await chromium.launch({ args: ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });

let problems = 0;
page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") { if (m.type() === "error") problems++; console.log(`[${m.type()}] ${m.text()}`); } });
page.on("pageerror", (e) => { problems++; console.log(`[pageerror] ${e.message}`); });
page.on("requestfailed", (r) => { problems++; console.log(`[requestfailed] ${r.url()}`); });

await page.route(`${ORIGIN}/**`, async (route) => {
  const rel = normalize(decodeURIComponent(new URL(route.request().url()).pathname)).replace(/^\/+/, "");
  const file = join(WEB, rel);
  if (!file.startsWith(WEB)) return route.fulfill({ status: 403 });
  try {
    const body = await readFile(file);
    await route.fulfill({ status: 200, body, contentType: TYPES[extname(file)] || "application/octet-stream" });
  } catch {
    await route.fulfill({ status: 404, body: "not found" });
  }
});

await page.goto(`${ORIGIN}/${path}`, { waitUntil: "load" });
const gl = await page.evaluate(() => {
  const c = document.createElement("canvas").getContext("webgl2");
  if (!c) return "no WebGL2";
  const d = c.getExtension("WEBGL_debug_renderer_info");
  return d ? c.getParameter(d.UNMASKED_RENDERER_WEBGL) : "WebGL2";
});
console.log(`[renderer] ${engine}: ${gl}`);
const js = opt("--js", null);
if (js) console.log(`[js] ${JSON.stringify(await page.evaluate(`(async () => { return ${js}; })()`))}`);
await page.waitForTimeout(Number(opt("--wait", "2000")));
if (args.includes("--fps")) {
  const t = await page.evaluate(() => new Promise((res) => {
    const times = []; let last = performance.now();
    const tick = (now) => { times.push(now - last); last = now; if (times.length < 120) requestAnimationFrame(tick); else res(times); };
    requestAnimationFrame(tick);
  }));
  t.sort((a, b) => a - b);
  console.log(`[frames] median ${t[60].toFixed(1)} ms, p95 ${t[114].toFixed(1)} ms (headless: indicative only)`);
}
await page.screenshot({ path: out });
console.log(`[shot] ${out}`);
await browser.close();
process.exit(problems ? 1 : 0);
