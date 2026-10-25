import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

// `base` IS the page's URL. It must equal the `nl2sql.pages` entry-point name in pyproject.toml (`accidents` →
// /page/roadsafety/): the app mounts the built folder there. A missing or wrong base loads the HTML and 404s the
// bundle — a blank page with no useful error (nl2sql-eda precedent).
export default defineConfig({
  plugins: [react()],
  base: "/page/roadsafety/",
  define: { __PLUGIN_VERSION__: JSON.stringify(pkg.version) },   // web/package.json tracks pyproject (tests/test_page.py)
  build: { outDir: "../nl2sql_roadsafety/webdist", emptyOutDir: true },
  server: {
    // P10: the dev server proxies the basemap to the running app — its verified Range-request path serves
    // the pmtiles; Vite serves basemap-assets/ (glyphs, sprites, rtl-text) from public/ by itself.
    proxy: { "/api": "http://localhost:8000", "/page/roadsafety/basemap": "http://localhost:8000" },
    fs: { allow: [".."] },                 // the Israel outline is imported from the Python package (one source of truth)
  },
});
