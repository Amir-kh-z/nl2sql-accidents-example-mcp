# P6 — Demo hardening (detailed plan)

## Context

P5 (`v0.5`, commit `0e1bc14`) closed the feature surface: 19 actions, the page, the studio, 285 tests. P6 makes the
SEMINAR run safe: the cassette recorder for the chat beat, automated pre-flight (the P4/P5 sweeps proved the stage
state can silently drift — the running app is a side door), the fresh-dir and shared-dir rehearsals with real
timings, `docs/demo/DEMO.md` (PLAN_2 finalized), and `plan_b.pdf` (the every-beat fallback deck). No new actions.
Version **0.6.0** (precedent: every phase bumps), commit `[P6]`, tag `v0.6`. The two PROJECTOR rehearsals stay the
instructor's task (they need Efraim's date) — DEMO.md carries their checklist.

## Facts the design rests on (verified read-only, 2026-09-02)

- The app configures cassettes at import: [adapters.py:60](app/api/adapters.py#L60)
  `nl2sql_engine.configure(cassette_dir=ROOT / "cassettes")`; `NL2SQL_REPLAY=1` → `configure(replay=True)` (line 69).
  `app\cassettes\` is the ONE sanctioned write under `app\` (gitignored). The engine's `Config` has
  `record: bool = False` — "save every live response for later replay"; `Cassettes.record()` writes one JSON per
  call (prompt kept for audit; LF-normalised). The cassette/replay code lives ONLY in the no-key CLI branch of
  `_call_claude` — with `ANTHROPIC_API_KEY` set the app calls live while `/health` still says replay (documented
  risk, PLAN_2 §7).
- `adapters.run_question(name, question, method=None, limit=None, last_sql=None, last_question=None, history=None)`
  is the Chat UI's own code path — calling it with the UI's default body (deployed method, empty history) builds
  the byte-same prompt, so the cassette hits on stage.
- Keyless chat works on this machine (P0 spike B, OAuth Max via the `claude` CLI): the two verified questions cost
  ~$0.20–0.27 equivalent each, 13–16 s. Recording spends that Max quota once per question.
- The chat beat needs at most TWO cassettes (PLAN_2 beat 1's optional variant): `כמה תאונות קלות היו ב-2024?`
  (→ 5,458, the trap held) and the backup `כמה הרוגים היו בתאונות דרכים ב-2024?` (→ 439).
- Stage state (owned by the instructor, re-verified after the P4 contamination): `models\site\` = deployed
  doc-11/2023 + rejected doc-11/2022 + rejected shuffled/2018 + `deployed.json` → the 2023 model; ledger 15 lines
  incl. the rehearsal `before_after` entry. All app copies share port 8000 + `%LOCALAPPDATA%\nl2sql-core`.
- Every chart/card the demo needs already renders its own committed-safe frame: the actions' `png_base64` twins
  carry the CBS credit in-image by construction. Committed frames = chart/ranking/card ONLY (never the points
  layer or a popup); a row-level fallback frame, if ever wanted, lives under `C:\data\demo\` (skipped by default,
  DEMO.md says how).

## Deliverables (all repo-side; `tools/` never enters the wheel)

1. **`tools/preflight.py`** — the automated PLAN_2 §0 table, one PASS/FAIL line each (exit 1 on any FAIL):
   port 8000 has at most the one expected listener; `ANTHROPIC_API_KEY` absent (when `--replay` is intended);
   `claude --version` responds; the data dir RE-VERIFIED (exactly the 3 seeded models, the pointer names the 2023
   model, ledger short with the rehearsal `before_after` entry present); the connection registry points
   `israel_accidents` at `C:\data\...duckdb` with sidecars beside it; plugin 0.6.0 + eda + shapes importable from
   `app\.venv`; optional `--live` probe (app already up): 19 actions, `problems: []`, page mounted. This is the
   direct product of the port-8000 pitfall.
2. **`tools/record_cassettes.py`** — run from `accidents-lab\` with the clone's venv, the LAST build step:
   refuses to run if `ANTHROPIC_API_KEY` is set (the bypass risk, stated in its output); `sys.path` → `app\`;
   `import api.adapters` (which sets cassette_dir); `nl2sql_engine.configure(record=True)`; per scripted question
   call `adapters.run_question("israel_accidents", q)` with the UI-default body; print answer/tokens/cost.
   Then the verification pass IN A SUBPROCESS with `NL2SQL_REPLAY=1`: same `run_question`, assert
   `usage.replayed == true`, cost 0, and the same headline number. The question list lives at the top of the file.
3. **Rehearsal A — fresh experience** (`NL2SQL_CORE_DATA_DIR=c:\tmp\demo-data`): stop the shared app, launch the
   clone against the empty dir, seed live through the studio (train 2023 → validate → deploy; train/validate the
   two rejections; the rehearsal `before_after`), then drive all five beats + 5b through their actions, timing
   each; tear down, relaunch the shared-dir app, re-run `tools/preflight.py` to prove the stage state survived.
4. **Rehearsal B — the stage run** (shared dir, no env var): the same beat script against the seeded dir; then
   trim the ledger back to the stage set (instructor-owned state, same operation as the P4/P5 restores) and
   preflight again. Both rehearsals' timings and outputs → **`docs/demo/rehearsal_p6.md`**.
5. **`docs/demo/DEMO.md`** — PLAN_2 §§0–7 finalized as the run-book: pre-flight = `tools/preflight.py` + the
   manual rows (projector, zoom, Plan-B window); per beat the EXACT inputs (the real site key, years, top_n),
   the rehearsed numbers to expect on screen, the spoken point, and the fallback; the projector-rehearsal
   checklist (the instructor's two runs, needs Efraim's date); the cassette story (record last, replay probe,
   the key-present bypass warning).
6. **`docs/demo/plan_b.pdf`** — one landscape frame per beat from the rehearsal run's own artifacts:
   beats 1/4 = the trap/refusal cards rendered to an image frame, beats 2/3/5b = the actions' PNG twins
   (segment_rates, hotspot_map excess, before_after, site_ranking, studio gate chart, studio_models table frame),
   beat 5 = a headless page capture of a CHART card on the accidents page + the Modules-page render. Assembled
   with matplotlib `PdfPages` (no new dependency). Every frame carries the in-image CBS credit; nothing row-level.
7. Docs: plan.md P6 row (+ deviations), README (a short "demo tooling" note), PITFALLS as they happen,
   PLAN_2 marked "superseded by docs/demo/DEMO.md" in its header. Version bump 0.6.0 (pyproject, `__init__`,
   package.json + `npm run build`) — the contract test pins it.

## Order of work

0. Save `docs/p6_design.md` (this plan); pre-flight by hand once (tree clean at v0.5, app runs, stage verified).
1. `tools/preflight.py` → run it green against the current stage.
2. The beat-driver script (shared by both rehearsals; lives in `tools/rehearse.py`, repo-side): runs the beats'
   actions through the module API with a Context per run — NOT through port 8000 when the shared dir is live
   (the side-door lesson); against the fresh dir it may use the running app. Timings collected.
3. Rehearsal A (fresh dir) → numbers into `rehearsal_p6.md`; stage re-verified after.
4. Rehearsal B (stage run) → numbers; ledger trimmed; preflight green.
5. `plan_b.pdf` from the rehearsal artifacts + the two page captures; eyeball every frame.
6. `DEMO.md`; version bump + webdist rebuild; suite + wheel sanity (delete `build\` first); restart + 19 actions.
7. **Cassettes LAST**: `tools/record_cassettes.py` (2 questions, ~$0.5 Max-quota equivalent) → replay probe
   green. If the CLI is not logged in at that moment, the recorder still ships and DEMO.md marks the chat variant
   cassette-pending (the action path carries beat 1 regardless).
8. **Sweep question** (I ask you first, as always): checkers over the recorder's key/replay logic, preflight's
   assertions vs the real stage, DEMO.md numbers vs the rehearsal log, plan_b frames vs the license rule
   (no row-level content), port-8000 discipline in the tools. Then the recap → your acceptance → `[P6]` + `v0.6`.

## Acceptance (from plan.md §P6, sharpened)

- [ ] `tools/preflight.py` green against the seeded stage; it FAILS loudly on a doctored dir (tested).
- [ ] Both rehearsals ran the full beat script without a fallback; timings recorded in `rehearsal_p6.md`;
      the shared dir ends in the exact stage state (preflight green after both).
- [ ] Cassettes recorded keylessly and the replay probe shows `replayed: true`, cost 0, same numbers;
      the key-present bypass documented in DEMO.md.
- [ ] `plan_b.pdf` committed with chart/ranking/card frames only; DEMO.md is the complete run-book.
- [ ] Suite green at 0.6.0; wheel sanity clean; 19 actions + `problems: []`; `git -C app status` clean
      (`app\cassettes\` is gitignored runtime state — verify it stays out of status).
- [ ] Sweep run (with your go); confirmed findings fixed. `[P6]` + `v0.6` after your acceptance.

## Risks / pitfall watch

The key-present bypass (recorder refuses; DEMO.md warns; preflight checks); cassette misses from prompt drift
(record LAST, clear chat history before the beat, the action path is the default); rehearsal B writes to the
stage ledger (trim after — instructor-owned); port 8000 single-instance discipline during the fresh-dir swap
(stop/start order scripted, never two apps); `NL2SQL_CORE_DATA_DIR` read once per process (fresh-dir app gets it
at launch, never exported in the shared shell); matplotlib cold font cache on the fresh dir's first chart
(~90 s — time it, it IS the warm-up row's number); plan_b frames must be re-generated if any caveat text changes
later (note in DEMO.md); nothing from `C:\data` or the Desktop folder enters the repo.

## As built (2026-09-02)

All seven deliverables shipped; deviations in plan.md's P6 row (module-level rehearsal A + the app-boot smoke;
usage via the engine's process-global `get_usage_cost`; ASCII-only table frame in plan_b). Numbers: preflight 9
checks green + the doctored-dir negative test (2 FAILs, exit 1); rehearsal A seeded a fresh dir live in ~3.3 s and
ran 11 beats ≤ 0.77 s each; rehearsal B (stage) all PASS; the app boots against `NL2SQL_CORE_DATA_DIR=c:\tmp\demo-data`
in ~2 s reporting the redirected dir with 19 actions; cassettes: both questions recorded keylessly ($0.26 + $0.17
would-have-been) and replay-verified (`replayed: true`, cost 0, 5,458/439 stable); `plan_b.pdf` 12 pages (cover +
4 card frames + 5 chart twins + 2 page shots), eyeballed — RTL correct, no row-level content; the stage dir ends
at the seeded set (preflight green after everything); `git -C app status` clean with 2 cassettes present
(gitignored). Wheel 0.6.0: 44 files, fresh bundle, no tool/doc leaks.

## Sweep (2026-09-02, 35 agents, run wf_37860dfb-d77)

10 confirmed (0 contested, 3 refuted with solid grounds), ALL fixed. The highs: (1) **chat history breaks cassette
replay on stage** — the Chat UI restores the `chat_history.json` sidecar into every /query body, changing the
sha256 cassette key; both shipped cassettes are empty-history, and 2 old turns sat in the sidecar RIGHT THEN. Fix:
a new preflight check (empty sidecar under --replay, FAIL otherwise), the sidecar cleared to `[]`, and DEMO.md's
one-question-per-fresh-conversation rule (the backup question is an alternative, never a follow-up). (2) preflight
accepted a **0-byte deployed model.ubj** (xgboost kills the process on it, exit 9, no traceback) — now a size floor
on all three models + a subprocess load probe of the deployed booster. (3) plan_b's **finding_card page carried the
triage refusal** ("latest" picked up the preceding card beat) — the tool now resolves the last before_after ledger
idx explicitly and refuses if the card lacks the evidence. Mediums/lows: connection check now validates sizes and
parses the sidecars; the port probe uses Get-NetTCPConnection (locale-independent, probe failure = FAIL);
make_plan_b refuses a --data-dir that IS the real stage dir; the models-card page states its scratch-registry ids;
DEMO.md's page references and rebuild command corrected. ALSO: the sweep contaminated the stage a THIRD way —
agents set NL2SQL_CORE_DATA_DIR after importing the engine (read-once) — restored again; the vector is appended to
the side-door PITFALLS entry, and preflight itself flagged the drift mid-sweep (the re-verification rule proving
itself). Deck rebuilt (12 pages); preflight 10 checks green + both negative tests.
