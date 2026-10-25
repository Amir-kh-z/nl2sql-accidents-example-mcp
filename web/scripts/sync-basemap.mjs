// P10: `vite build` wipes webdist/ (emptyOutDir), so the big untracked basemap files must be re-placed after
// every build. NTFS hardlinks are instant and are REAL files (the app's StaticFiles rejects symlinks via its
// realpath containment check — a hardlink passes); copy is the cross-volume fallback. No-op with a note when
// the cache is empty: the page then runs in the canvas-fallback style, which is a supported mode, not an error.
import { copyFileSync, existsSync, linkSync, mkdirSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const cache = join(here, "..", "basemap");                                  // web/basemap/ (gitignored)
const dest = join(here, "..", "..", "nl2sql_roadsafety", "webdist", "basemap");

if (!existsSync(cache)) {
  console.log("[sync-basemap] web/basemap/ absent - the page will run in the canvas fallback style");
  process.exit(0);
}
const files = readdirSync(cache).filter((f) => statSync(join(cache, f)).isFile());
if (files.length === 0) {
  console.log("[sync-basemap] web/basemap/ empty - the page will run in the canvas fallback style");
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
for (const f of files) {
  const from = join(cache, f);
  const to = join(dest, f);
  if (existsSync(to)) unlinkSync(to);
  try {
    linkSync(from, to);                                                     // hardlink: zero-copy on one volume
    console.log(`[sync-basemap] hardlinked ${f} (${statSync(to).size.toLocaleString()} B)`);
  } catch {
    copyFileSync(from, to);
    console.log(`[sync-basemap] copied ${f} (${statSync(to).size.toLocaleString()} B)`);
  }
}
