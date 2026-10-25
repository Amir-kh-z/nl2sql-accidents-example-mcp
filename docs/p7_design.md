# P7 — Wrap (detailed plan)

## Context

P6 (`v0.6`, commit `d4b4378`) hardened the demo; the feature surface (19 actions, page, studio, tooling) is done
and the stage is verified. P7 closes the pathfinder: the pitfall ledger becomes a categorized reference, the
participant-scoping input gets written, the handoff docs (README/CHANGELOG) land, version goes to **0.7.0**, the
release wheel is built FROM THE COMMITTED TREE (no index publish — that needs your explicit yes, later), and the
`context\` pack is refreshed so any future session starts warm. Commit `[P7]`, tag `v0.7`. Data-dir state: shared
seeded, unchanged. After P7 the remaining work is yours: the two projector rehearsals (Efraim's date) and the
participant-scoping decision (which `participants.md` feeds).

## Deliverables

1. **PITFALLS.md consolidation** — keep the entries chronological ("recorded when they happen" stays literal),
   ADD: a category tag on every `##` heading (suffix ` · [category]`) and a **category index table** at the top
   (category → entry titles). Categories: the planned seven (packaging / API / SQL / RTL / map / demo / license)
   **plus two the material demands** (recorded as a deviation): `concurrency` (os.replace vs Windows readers) and
   `state` (the shared-data-dir side-door family, three vectors). ~33 entries.
2. **`docs/participants.md`** — the input for the scoping decision you make after P7:
   the **teachable band** (which of the 19 actions a participant team can realistically re-derive: the analytical
   tier P1–P2 yes; the page = template + precedent; the studio = advanced/optional with the gate as the teaching
   point; what stays instructor-owned: license discipline, the seeded stage);
   the **planning prompt** participants would receive (derived from the kickoff's own structure: dossier-first,
   golden rules, phase discipline, PITFALLS-as-curriculum — the "what the real build & participants should do"
   lines are the syllabus);
   the **seed skeleton proposal** (what a starter repo ships: envelope.py + sqlkit's case/key/coercion helpers +
   the contract tests + an empty action, per the template precedent).
3. **Handoff docs**: `CHANGELOG.md` (v0.0 → v0.7, one block per phase from plan.md's Progress rows, deviations
   included); README polish (status → P7/handoff, link DEMO.md + participants.md + CHANGELOG, the license rules
   and install ±`[ml]` stay).
4. **Version 0.7.0** everywhere: pyproject, `__init__`, web/package.json (+ `npm run build`),
   tests/test_contract.py pin, **tools/preflight.py `PLUGIN_VERSION`** (the P6 sweep flagged the hard-coded
   constant — this bump is the test of that note). Suite re-run (285 expected).
5. **Context refresh** (in `accidents-lab\context\`, allowed — not `app\`):
   a status header on `PROMPT_TASK4_PATHFINDER_KICKOFF.md` (agenda SETTLED; the plugin repo's `docs/plan.md`,
   `CLAUDE.md`, `PITFALLS.md`, `docs/demo/DEMO.md` are now the authoritative state; open externals: Efraim's
   date + the scoping decision);
   an addendum section on `DOSSIER_TASK4_ACCIDENTS_DB.md`: what the build AMENDED or discovered beyond the dossier
   (the `road_km = 0` both-sides rule and 70.4 % coverage, the `99999999` junction sentinel, the one-row street-pair
   rule, the shape-code-9 timeline 5 %→24 %→47 %, the 2009 involved gap handling, the fleet-cohort undercount in
   `v_motorcycle_accident_rate`, code 22 = mobility scooter) with pointers to `sqlkit.py`/`PITFALLS.md` as the
   living reference.
6. **Release from the committed tree** (post-acceptance, after `[P7]` + `v0.7`): delete `build\`, build
   `nl2sql_accidents-0.7.0-py3-none-any.whl` from the tagged tree, namelist check, wheel-install smoke on the
   clone (19 actions, `problems: []`), `-e` restored. The wheel stays in `dist\` (gitignored) — **NO index
   publish** without your explicit yes.
7. **Memory + wrap**: update the memory note (Task-4 pathfinder COMPLETE through v0.7; what remains is the user's).

## Order of work

0. Save `docs/p7_design.md`; pre-flight (tree clean at v0.6, `tools/preflight.py --replay --live` green).
1. PITFALLS categorization (index + tags).
2. `docs/participants.md`.
3. CHANGELOG.md + README polish.
4. 0.7.0 bump (incl. preflight's constant) + webdist rebuild + `-e` metadata refresh + full suite + app restart
   probe (19 actions, page serves the new bundle).
5. Context refresh (kickoff header + dossier addendum).
6. **Sweep question** (I ask you first): a light docs-vs-reality pass — the CHANGELOG/participants/dossier-addendum
   claims against plan.md and the code, the category tags against the entries, version consistency. If declined or
   credits object, inline verification.
7. Recap → your acceptance → `[P7]` commit + `v0.7` tag → the release-wheel build from the committed tree →
   install smoke → `-e` restore → final preflight. Then the pathfinder is wrapped.

## Acceptance (from plan.md §P7)

- [ ] PITFALLS categorized (index + per-entry tags, chronology preserved); `docs/participants.md` complete enough
      to hand to the scoping discussion; CHANGELOG covers v0.0–v0.7.
- [ ] Suite green at 0.7.0; preflight green (its own version pin updated); 19 actions + `problems: []`;
      `git -C app status` clean; stage dir unchanged.
- [ ] Context pack refreshed (kickoff status header + dossier addendum) — a fresh session starting from
      `context\` lands on the current truth.
- [ ] Release wheel built from the COMMITTED `v0.7` tree, verified, not published.
- [ ] Sweep run or inline-verified (your call). `[P7]` + `v0.7` only after your acceptance word.

## Risks / pitfall watch

The version bump has FOUR touch points now (pyproject / `__init__` / package.json / preflight) — the contract test
pins three, preflight's own run pins the fourth; delete `build\` before the release wheel (the stale-assets
pitfall); the dossier addendum must AMEND, not rewrite (the dossier is the knowledge base — additions only, dated);
the kickoff header must not break its pasteable-prompt section; nothing from `C:\data` enters the repo; the
context files are outside the plugin repo — they are NOT part of the `[P7]` commit (note it in the recap).

## As built + sweep (2026-09-02, 18 agents, run wf_4adc5671-ecf)

All deliverables shipped. Sweep: 8 confirmed (0 contested, 1 refuted), ALL fixed — the highs: (1) plan.md's
Progress table (the declared ground truth) lagged its own story — P6 unaccepted, no P7 row, while CHANGELOG/README
pointed readers at it (both rows now written); (2) the dossier addendum's "2,329 casualty accidents in 2024" was
the PANEL Σy, not the national 8,315 (scoped properly, and the same qualifier added to the PITFALLS gate entry);
(3) the kickoff STATUS block overclaimed "v0.7, all phases accepted" before the tag exists (reworded to be true
pre- and post-tag; flips at the tag). Also: PITFALLS reordered to STRICTLY reverse-chronological (a pre-existing
misorder the "chronology preserved" claim exposed), the page-defects entry retagged [RTL]→[page] (1/8 sub-defects
were RTL; the category note updated), the v0.4 date aligned to the immutable tag (2026-09-02), the dossier
addendum renumbered §13→§12 (no phantom gap) and its shape-9 chain scoped (casualty-row timeline vs both-series
57 %, casualty-only 34 %). Stage verified untouched by this sweep (3 models, 15 lines — the guardrails held).
