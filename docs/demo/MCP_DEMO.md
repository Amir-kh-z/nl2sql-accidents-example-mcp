# MCP_DEMO.md — the chat-channel recording (Claude Desktop, ~12 min)

> **Course participants:** this is the instructor's recording script, and its pre-flight (§0) describes the
> instructor's stage machine (paths under `accidents-lab\`, the seeded 18-line ledger, `preflight.py`). On your
> own machine the preparation is `seed-models.bat` once; then the same ten prompts work in Claude Code or Claude
> Desktop, and the numbers to check are those in `docs/mcp_acceptance.md` and in the README's question set.

**The take:** one conversation in Claude Desktop over the `roadsafety` connector — the ten steps of the deck's last
slide (`mcp_roadsafety_he.pptx`, slide 17), in that order. Made for the course participants; the
instructor drives. The expected values are the pinned acceptance numbers (`docs/mcp_acceptance.md`, pinned
2026-10-16 against the seeded registry). Check the numbers, not the wording — the model's prose varies per take.

**CBS rules for the video.** Internal use: data at any level may appear on screen, but keep the frames to charts,
rankings and cards (no map points layer, no popups — the seminar's frame rule in `DEMO.md`). Open on the deck's
title or agenda slide (the footer carries the CBS credit) and let at least one answer's credit line be readable.
Share the video with the class; it is not part of this repository.

## 0 · Pre-flight (T−20 min)

```powershell
cd c:\Users\A\dev\accidents-lab
# 1. App STOPPED (Ctrl+C in its shell). Trim the stage ledger to the seeded 18 lines; a timestamped backup stays beside it.
app\.venv\Scripts\python -c "import os, shutil, pathlib, time; p = pathlib.Path(os.environ['LOCALAPPDATA'], 'nl2sql-core', 'accidents', 'ledger.jsonl'); b = p.with_name('ledger.backup-' + time.strftime('%Y%m%d-%H%M%S') + '.jsonl'); shutil.copy2(p, b); lines = p.read_bytes().splitlines(keepends=True); keep = lines[:18]; assert b'before_after' in b''.join(keep), 'seeded set not found'; p.write_bytes(b''.join(keep)); print(len(lines), 'lines ->', len(keep), '| backup:', b.name)"
# 2. In a SECOND shell: start the app (it opens http://localhost:8000); open the 🚦 tab → ממצאים, fresh.
.\app\run.ps1
# 3. Back in the first shell. Expect PREFLIGHT GREEN: stage ledger 18 lines, registry 3 site + 1 severity.
app\.venv\Scripts\python nl2sql-accidents-plugin\tools\preflight.py --live
```

- **One app copy only.** Every NL2SQL app copy on this machine shares the stage data dir, whatever its port; stop the
  others before step 1 (on 2026-10-24 a second copy was serving port 8010 from `Desktop\NL2SQL Closed Core Example`).
- **Claude Desktop:** quit it fully (tray icon → Quit, not just the window) and reopen, so the connector starts
  fresh on 0.14.3. Open a **new chat**; `roadsafety` is on in its tools menu.
- **The studio tool must still ask.** If you ever chose to always allow `roadsafety_studio`, reset that in Desktop's
  connector settings first — step 9 is the approval prompt.
- **Screen:** notifications off (Do not disturb), other windows closed, Desktop zoomed until the Hebrew reads
  comfortably (Ctrl +), the app's browser window ready behind it. Any recorder works; Snipping Tool's video mode
  (Win+Shift+R) is built in. The first chart of a fresh connector takes a few seconds longer.

## 1 · The ten steps — type exactly this, check exactly that

Each step is one message in the same chat. "Say" is a one-line voice-over; "If not" is the recovery message.

**1 · Orientation** — type `מה המסד הזה ומה אפשר לשאול?`
- Check: `roadsafety_orient` (about) — the CBS road-accidents database, data to **31.12.2024**, rows per series, the
  golden rules, the two deployed models (`site-2023-doc11…`, `severity-2022-person12…`).
- Say: before answering anything, the agent reads what this database is and what its rules are.
- If not: `התחל מ-roadsafety_orient.`

**2 · The trap** — type `למה ספירה נאיבית של תאונות קלות ב-2024 נותנת מספר גדול פי תשע?`
- Check: `roadsafety_orient section=trap` → naive_vs_correct — **50,145** vs **5,458**, ≈ **9.2×**; the two series in
  one table (`case_type_code`) explained.
- Say: the rule lives in the tool, not in the model's memory; an agent writing free SQL falls straight into it.
- If not: `השתמש ב-roadsafety_orient עם section=trap.`

**3 · Trend** — type `כמה הרוגים היו בתאונות דרכים ב-2024, ומה המגמה מ-2019?`
- Check: `roadsafety_trend` — 355 · 305 · 364 · 351 · 361 · **439**; a chart; "ספירות בלבד"; the credit line.
- Say: 439, and the legend under the table says what each column is. Counts, not risk.

**4 · Where is it dangerous** — type `איפה הכי מסוכן בכביש 60 — ביחס למה שהמודל מצפה?`
- Check: `roadsafety_sites rank_by=excess road=60` — **60/850** כניסה לעפרה–צומת תפוח: observed **113**, expected
  **73.3**, excess **+39.7**, significant, **rank 1 of 21**; second 60/823 +13.6 (not significant).
- Say: dangerous means above what the model expects for that traffic, not the biggest count.
- If it ranks raw counts: `דרג לפי עודף מעל הצפוי (rank_by=excess).`

**5 · A name becomes a key** — type `מה קורה בצומת העשור? יש לו מודל?`
- Check: `roadsafety_find` (העשור → `njunction:433`), then `roadsafety_site` — the yearly strip and **no model
  measures**: junctions have no exposure denominator, and the caveat says so.
- Say: the researcher used a name; the tool found the key, and it says what it cannot say.
- If not: `חפש את הצומת עם roadsafety_find.`

**6 · Did the change work** — type `האם השינוי ב-2017 בכביש 60 בין ק״מ 96.0 ל-98.8 עבד?`
- Check: `roadsafety_change_effect` → before_after (window 3) — casualty accidents 49 → 6 against the network
  38,867 → 36,102: ratio **0.13**; damage-only 1.25; **double ratio 0.11** (0.04–0.29); "association, not proof".
- Say: the double ratio nets out the national trend, and it still says association, not proof.
- If it picks another site: `השתמש באתר road:60/96.0-98.8 ושנת שינוי 2017.` (A bare "60/96" would mean segment 96.)

**7 · The finding card, and the page** — type `הפוך את זה לכרטיס ממצא.` RIGHT after step 6
- Check: `roadsafety_finding op=card` — `entry=latest` is the before/after: claim · evidence (0.11) · caveats · rerun
  recipe · credit.
- Then switch to the browser: 🚦 → ממצאים → `ledger_list` — the top entry is the chat's before_after, same inputs —
  then `finding_card` with `entry=latest`, `claim=באתר המטופל הספירה ירדה מתחת לציפייה` → the same card.
- Say: the same number in the chat, on the page and in the ledger — one engine, three doors.
- If it cards something else: `הצג את הפנקס והפוך את רשומת ה-before_after לכרטיס.`

**8 · What-if** — type `מה ההבדל בסיכון לחומרה בין חגור ללא חגור?`
- Check: `roadsafety_predict` → what_if — killed **×1.38**, severe **×1.28**, slight **×0.21**; "יחסי בלבד".
- Say: relative only — a model's ratio, never a person's fate.

**9 · Governance** — type `אמן מודל אתר חדש עם train_until 2021.`, then `בדוק את מודל האתר הפרוס.`
- Check (train): the model explains and asks in the chat — answer `כן, אמן` — and Desktop shows its approval
  prompt for `roadsafety_studio`: click **Deny**. The answer: nothing was trained.
- Check (validate): approve **once**. `roadsafety_studio op=validate` on the deployed model passes its gate —
  Spearman **0.693**, calibration **1.173** (gate: Spearman ≥ 0.3, calibration within 25 %).
- Say: two locks — the model asks, then the app asks a human. Checking a model is allowed; changing one needs a person.
- If not: never choose "always allow". If no prompt appears and training starts, let it finish and remove the new
  model after the take (§2). If validate reports a different model: `את הפרוס: site-2023-doc11-s42-20260901T130342.`
  (Verified 2026-10-24 on a scratch copy of the registry: the deployed model and "latest" give the same card.)

**10 · A refusal** — type `איזה דגם רכב הכי בטוח?`
- Check: `roadsafety_triage` — a **refusal**: no make, model, plate or VIN in the CBS files; the alternative is the
  vehicle cells (manufacture year × engine band).
- Say: a refusal with its reason and an alternative is an answer too.

End the take on this answer, or cut back to the deck's slide 17.

## 2 · After the take

```powershell
cd c:\Users\A\dev\accidents-lab
# 1. What the chat called: one audit line per tool call, none ERROR
app\.venv\Scripts\python -c "import os, json, pathlib; p = pathlib.Path(os.environ['LOCALAPPDATA'], 'nl2sql-core', 'accidents', 'mcp_audit.jsonl'); rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()][-16:]; [print(r['ts'][:10], r['ts'][11:19], r['tool'], ','.join(a['action'] for a in r['actions']) or '-', 'ERROR' if r['error'] else 'ok') for r in rows]"
# 2. The registry must still be the seeded set (the app is running: --live)
app\.venv\Scripts\python nl2sql-accidents-plugin\tools\preflight.py --live
# 3. Stop the app, then trim the ledger back: the same command as pre-flight step 1.
```

- Preflight's **stage registry** line fails only if a model was trained by mistake. The seeded site models are
  `site-2023-doc11-s42-20260901T130342` (deployed), `site-2022-doc11-s42-20260901T130343` and
  `site-2018-shuffled-s42-20260901T130343`; delete only the one new folder beside them under
  `%LOCALAPPDATA%\nl2sql-core\accidents\models\site\` — never `deployed.json` — and rerun preflight.
- Save the video outside the repo. Any stumble → `PITFALLS.md` the same day.

## 3 · If a take fails

Re-record — nothing in the conversation is precious; start a new chat and trim the ledger again. The deck carries
the same numbers (slides 7–11), and `plan_b.pdf` carries the page frames.
