# -*- coding: utf-8 -*-
"""The tool catalog: twelve intent-grouped tools over the plugin's actions (the course owner's rule — a tool is a
name and an intent, the action is the computation; grouping is a design decision, not a mechanical export,
so the model's context holds twelve descriptions instead of thirty).

Every tool is a closure over a Runner; the closures are typed so the SDK derives each input schema from
the signature (Literal = enum, `int | None` = optional with the action's own default). Hebrew choice
values pass through verbatim — they ARE the actions' contract. Nothing here imports the SDK: `wrap`
converts a ToolResult at the boundary (server.py), tests call the closures directly.

Governance: `roadsafety_studio` is the only tool that changes state, and its train/deploy ops REFUSE
without `confirm=True` — the text says what would happen, so the model can ask the person first."""
import contextvars
import inspect
from dataclasses import dataclass
from typing import Callable, Literal

from .. import MODULE
from . import lookup
from .render import ToolResult, to_result
from .runner import Runner, Step

try:   # the SDK injects its Context into a parameter annotated with this class (M2: the elicitation gate);
    from mcp.server.mcpserver import Context as _Context   # without the SDK the annotation is inert
except ImportError:  # pragma: no cover
    class _Context:  # type: ignore[no-redef]
        """Placeholder when the mcp SDK is absent — tools are then only called directly (tests, scripts)."""

# ── the map: every action is either behind a tool or excluded on purpose (pinned by tests) ─────────────
TOOL_ACTIONS: dict[str, tuple[str, ...]] = {
    "roadsafety_orient": ("about", "studio_models", "naive_vs_correct"),
    "roadsafety_trend": ("trend",),
    "roadsafety_breakdown": ("severity_profile", "heat_matrix", "weather_check"),
    "roadsafety_sites": ("site_ranking", "segment_rates", "hotspot_map", "zone_ranking", "city_ranking"),
    "roadsafety_site": ("site_profile", "studio_explain"),
    "roadsafety_change_effect": ("before_after", "ab_scan"),
    "roadsafety_vehicles": ("vehicle_cells_ranking", "two_wheelers"),
    "roadsafety_predict": ("severity_predict", "what_if"),
    "roadsafety_explain": ("severity_explain", "studio_explain"),
    "roadsafety_studio": ("studio_train_site", "studio_train_severity", "studio_validate",
                          "studio_validate_severity", "studio_deploy"),
    "roadsafety_finding": ("ledger_list", "finding_card"),
    "roadsafety_triage": ("triage",),
    "roadsafety_find": (),             # M2: a navigation helper over names → site keys; no action behind it
}
# page-only: the interactive map's 300k-point cloud is a GPU payload, not a chat answer; hotspot_map's
# individual-accident points (row level) are likewise never requested from here
EXCLUDED_ACTIONS = frozenset({"map_scene"})
STATE_CHANGING_OPS = ("train", "deploy")

Face = Literal["auto", "table", "sql", "card"]
Family = Literal["site", "severity"]
UNSET = "לא צוין"
RoadType = Literal["לא צוין", "עירוני בצומת", "עירוני לא בצומת", "לא-עירוני בצומת", "לא-עירוני לא בצומת"]
TimeOfDay = Literal["לא צוין", "יום", "לילה"]
Casualty = Literal["לא צוין", "הולך רגל", "נהג רכב", "נוסע רכב", "רוכב אופנוע", "רוכב אופניים"]
Age = Literal["לא צוין", "ילד עד גיל עשר", "צעיר", "מבוגר", "ותיק", "קשיש"]
Safety = Literal["לא צוין", "חגור או קסדה", "ללא אמצעי בטיחות"]
Speed = Literal["לא צוין", "עד חמישים", "שבעים", "תשעים", "מאה ומעלה"]
Switch = Literal["none", "יום לעומת לילה", "חגור לעומת לא חגור", "עירוני לעומת לא-עירוני", "חמישים לעומת תשעים"]
Breakdown = Literal["casualty_type", "road_type", "day_night", "age_group", "weather", "involved_vehicle_type",
                    "sex", "lighting", "hour_of_day", "day_of_week", "speed_limit", "road_shape", "year",
                    "day_hour", "weather_vs_measured"]
ExplainFeature = Literal["none", "casualty_type_code", "age_group_code", "sex_code", "safety_equipment_code",
                         "population_group_code", "involved_vehicle_type_code", "road_type_code", "day_night_code",
                         "speed_limit_code", "hour_of_day", "month", "year_idx"]

CONFIRM_TEXT = {
    "train": ("אימון מודל {family} הוא פעולה שמשנה מצב: נרשם מודל חדש (מועמד) ברישום המודלים תחת תיקיית הנתונים "
              "המשותפת של האפליקציה. לא בוצע דבר. אם המשתמש אישר במפורש, קראו שוב עם confirm=true."),
    "deploy": ("פריסת מודל {family} משנה את המצביע הפרוס — כל תשובה של דירוג/תחזית תשתמש בו מעתה. לא בוצע דבר. "
               "אם המשתמש אישר במפורש, קראו שוב עם confirm=true. פריסה מסרבת למודל שנדחה או שלא אומת."),
}


@dataclass
class ToolDef:
    name: str
    description: str
    fn: Callable[..., object]
    read_only: bool = True


def _action(name):
    return MODULE.action(name)


def view_for(action: str, face: str) -> str | None:
    """Translate the tool's `face` into this action's own `view` choice: auto = the chart spec when the
    action draws one (it carries the full answer), else the declared default; an unavailable face
    falls back to the default rather than erroring — a chat asks, it does not fill forms."""
    decl = _action(action).inputs.get("view")
    if decl is None:
        return None
    wanted = {"auto": "chart", "table": "table", "sql": "sql", "card": "markdown"}[face]
    return wanted if wanted in decl.choices else decl.default


def _render(step: Step, face: str, image: bool) -> ToolResult:
    return to_result(step.result, image=image, with_sql=(face == "sql" and step.result.kind == "chart"))


def catalog_text() -> str:
    """The tool↔action map as text — the `roadsafety://catalog` resource and orient(section=catalog)."""
    lines = ["# קטלוג הכלים · Road Safety Lab MCP", ""]
    for tool, actions in TOOL_ACTIONS.items():
        lines.append(f"## {tool}")
        for a in actions:
            act = _action(a)
            ins = ", ".join(f"{k}={v.default!r}" for k, v in act.inputs.items() if k != "view")
            lines.append(f"- {a} ({act.label}) — {act.help}")
            if ins:
                lines.append(f"  defaults: {ins}")
    lines += ["", "## excluded (page-only)"] + [f"- {a}" for a in sorted(EXCLUDED_ACTIONS)]
    return "\n".join(lines)


def build_tools(runner: Runner, *, wrap: Callable[[ToolResult], object] = lambda r: r,
                images: bool = True) -> list[ToolDef]:
    """The twelve tools as closures over one Runner. `wrap` converts ToolResult at the SDK boundary."""

    steps_var: contextvars.ContextVar[list] = contextvars.ContextVar("roadsafety_mcp_steps")

    def guarded(name: str):
        """Every tool: the DB-missing sentence first, then audit whatever ran (also refusals with no steps).
        The public function keeps the decorated function's exact signature — the SDK derives the input
        schema from it — and the per-call step list travels in a context variable, never a parameter."""
        def deco(fn):
            def _audit_args(kw):
                return {k: v for k, v in kw.items() if not isinstance(v, _Context)}   # never the SDK context

            if inspect.iscoroutinefunction(fn):
                async def inner(**kw):
                    missing = runner.db_missing()
                    if missing:
                        runner.audit(name, _audit_args(kw), [], note="db missing")
                        return wrap(ToolResult.text(f"שגיאה: {missing}", is_error=True))
                    token = steps_var.set([])
                    try:
                        out = await fn(**kw)
                        runner.audit(name, _audit_args(kw), steps_var.get(), note=getattr(out, "note", ""))
                    finally:
                        steps_var.reset(token)
                    return wrap(out)
            else:
                def inner(**kw):
                    missing = runner.db_missing()
                    if missing:
                        runner.audit(name, _audit_args(kw), [], note="db missing")
                        return wrap(ToolResult.text(f"שגיאה: {missing}", is_error=True))
                    token = steps_var.set([])
                    try:
                        out = fn(**kw)
                        runner.audit(name, _audit_args(kw), steps_var.get(), note=getattr(out, "note", ""))
                    finally:
                        steps_var.reset(token)
                    return wrap(out)
            inner.__signature__ = inspect.signature(fn)      # real annotations: no future-import strings here
            inner.__annotations__ = dict(fn.__annotations__)
            inner.__name__, inner.__qualname__, inner.__doc__ = fn.__name__, fn.__qualname__, fn.__doc__
            inner.__module__ = fn.__module__
            return inner
        return deco

    def one(action, face="auto", **inputs) -> ToolResult:
        view = view_for(action, face)
        if view is not None:
            inputs["view"] = view
        step = runner.run(action, **inputs)
        steps_var.get().append(step)
        return _render(step, face, images)

    # ── 1 · orient ────────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_orient")
    def roadsafety_orient(section: Literal["about", "models", "trap", "catalog"] = "about",
                          family: Family = "site", year: int = 2024, face: Face = "auto"):
        if section == "about":
            return one("about", face)
        if section == "models":
            return one("studio_models", face, family=family)
        if section == "trap":
            return one("naive_vs_correct", "sql" if face == "sql" else "card", year=year)
        return ToolResult.text(catalog_text())

    # ── 2 · trend ─────────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_trend")
    def roadsafety_trend(measure: Literal["accidents", "killed", "severe_injured", "slight_injured",
                                                 "fatal_accidents"] = "killed",
                         granularity: Literal["year", "month"] = "year",
                         road_type: Literal["all", "urban", "nonurban"] = "all",
                         from_year: int | None = None, to_year: int | None = None, face: Face = "auto"):
        return one("trend", face, measure=measure, granularity=granularity, road_type=road_type,
                   from_year=from_year, to_year=to_year)

    # ── 3 · breakdown ─────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_breakdown")
    def roadsafety_breakdown(by: Breakdown = "casualty_type", from_year: int | None = None,
                             to_year: int | None = None, display: Literal["shares", "counts"] = "shares",
                             rain_threshold_mm: Literal["0.1", "0", "0.5", "1"] = "0.1", face: Face = "auto"):
        if by == "day_hour":
            return one("heat_matrix", face, from_year=from_year, to_year=to_year)
        if by == "weather_vs_measured":
            return one("weather_check", face, from_year=from_year, to_year=to_year,
                       rain_threshold_mm=rain_threshold_mm)
        return one("severity_profile", face, by=by, from_year=from_year, to_year=to_year, display=display)

    # ── 4 · sites ─────────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_sites")
    def roadsafety_sites(rank_by: Literal["excess", "rate", "observed", "zones", "cities"] = "excess",
                         road: int = 0, from_year: int | None = None, to_year: int | None = None,
                         top_n: int | None = None,
                         unit: Literal["segments", "njunctions", "ujunctions"] = "segments",
                         severity: Literal["all", "ksi"] = "all",
                         measure: Literal["default", "per_capita", "density", "total", "ped_share"] = "default",
                         land_use: Literal["all", "1", "2", "3", "4", "5"] = "all", min_pop: int | None = None,
                         face: Face = "auto"):
        m = None if measure == "default" else measure
        if rank_by == "excess":
            return one("site_ranking", face, road=road, from_year=from_year, to_year=to_year, top_n=top_n)
        if rank_by == "rate":
            return one("segment_rates", face, road=road, from_year=from_year, to_year=to_year,
                       severity=severity, top_n=top_n)
        if rank_by == "observed":
            return one("hotspot_map", face, unit=unit, road=road, from_year=from_year, to_year=to_year,
                       top_n=top_n, points=False)
        if rank_by == "zones":
            return one("zone_ranking", face, measure=m, land_use=land_use, min_pop=min_pop, top_n=top_n)
        return one("city_ranking", face, measure=m, top_n=top_n)

    # ── 5 · one site ──────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_site")
    def roadsafety_site(site: str = "60/836", from_year: int | None = None, to_year: int | None = None,
                        drivers: bool = False, face: Face = "auto"):
        out = one("site_profile", face, site=site, from_year=from_year, to_year=to_year)
        if drivers and not site.startswith(("njunction:", "ujunction:")):
            out = out + one("studio_explain", "card", site=site)
        return out

    # ── 6 · change effect ─────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_change_effect")
    def roadsafety_change_effect(mode: Literal["evaluate", "discover"] = "evaluate",
                                 site: str = "road:60/96.0-98.8", change_year: int = 2017,
                                 window_years: int | None = None, min_cell: int | None = None, road: int = 0,
                                 top_n: int | None = None, from_year: int | None = None,
                                 to_year: int | None = None, face: Face = "auto"):
        if mode == "discover":
            return one("ab_scan", face, from_year=from_year, to_year=to_year, window_years=window_years,
                       min_cell=min_cell, road=road, top_n=top_n)
        return one("before_after", face, site=site, change_year=change_year, window_years=window_years,
                   min_cell=min_cell)

    # ── 7 · vehicles ──────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_vehicles")
    def roadsafety_vehicles(kind: Literal["cells", "cohort", "two_wheelers"] = "cells",
                            metric: Literal["involvements", "ksi", "fatal"] = "involvements",
                            bands: Literal["all", "known_engine"] = "all", from_year: int | None = None,
                            to_year: int | None = None, face: Face = "auto"):
        if kind == "two_wheelers":
            return one("two_wheelers", face, metric="fatal" if metric == "fatal" else "accidents",
                       from_year=from_year, to_year=to_year)
        return one("vehicle_cells_ranking", face, metric=metric, bands=bands,
                   group="cohort" if kind == "cohort" else "cell")

    # ── 8 · predict ───────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_predict")
    def roadsafety_predict(road_type: RoadType = UNSET, time: TimeOfDay = UNSET, casualty: Casualty = UNSET,
                           age: Age = UNSET, safety: Safety = UNSET, speed: Speed = UNSET,
                           switch: Switch = "none", face: Face = "auto"):
        profile = dict(road_type=road_type, time=time, casualty=casualty, age=age, safety=safety, speed=speed)
        if switch != "none":
            return one("what_if", face, switch=switch, **profile)
        return one("severity_predict", face, **profile)

    # ── 9 · explain ───────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_explain")
    def roadsafety_explain(family: Family = "severity", severity_class: Literal["הרוג", "פצוע קשה"] = "הרוג",
                           feature: ExplainFeature = "none", sample: Literal["20k", "50k", "full"] = "20k",
                           site: str = "", model_id: str = "deployed",
                           style: Literal["פרופיל", "נחיל"] = "פרופיל", face: Face = "auto"):
        if family == "site":
            return one("studio_explain", face, site=site, model_id=model_id, style=style)
        return one("severity_explain", face, model_id=model_id, severity_class=severity_class,
                   sample=sample, feature=feature)

    # ── 10 · studio (the one state-changing tool) ─────────────────────────────────────────────────────
    @guarded("roadsafety_studio")
    async def roadsafety_studio(op: Literal["train", "validate", "deploy"] = "validate", family: Family = "site",
                                train_until: int | None = None,
                                features: Literal["default", "doc-11", "person-12", "shuffled"] = "default",
                                seed: int | None = None, model_id: str = "latest", confirm: bool = False,
                                face: Face = "auto", ctx: _Context | None = None):
        if op in STATE_CHANGING_OPS:
            verdict = await hard_gate(ctx, op, family, train_until=train_until, features=features, model_id=model_id)
            if verdict == "declined":
                out = ToolResult.text("# ⛔ האדם דחה את הפעולה\n" + f"{op} ({family}) לא בוצע. לא השתנה דבר.")
                out.note = "declined " + op   # type: ignore[attr-defined]
                return out
            if verdict == "unavailable" and not confirm:
                out = ToolResult.text("# ⏸ נדרש אישור\n" + CONFIRM_TEXT[op].format(family=family))
                out.note = "unconfirmed " + op   # type: ignore[attr-defined] — audit hint only
                return out
        f = None if features == "default" else features
        if op == "train":
            action = "studio_train_site" if family == "site" else "studio_train_severity"
            return one(action, face, train_until=train_until, features=f, seed=seed)
        if op == "validate":
            action = "studio_validate" if family == "site" else "studio_validate_severity"
            return one(action, face, model_id=model_id)
        return one("studio_deploy", face, model_id=model_id, family=family)

    # ── 13 · find a site by name (M2) ─────────────────────────────────────────────────────────────────
    @guarded("roadsafety_find")
    def roadsafety_find(name: str, kind: Literal["all", "segments", "njunctions", "ujunctions", "cities"] = "all",
                        limit: int = 10):
        return ToolResult.text(lookup.find(runner.ctx, name, kind=kind, limit=limit))

    # ── 11 · findings ─────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_finding")
    def roadsafety_finding(op: Literal["list", "card"] = "list", last_n: int | None = None,
                           entry: str = "latest", claim: str = ""):
        if op == "card":
            return one("finding_card", "card", entry=entry, claim=claim)
        return one("ledger_list", "auto", last_n=last_n)

    # ── 12 · triage ───────────────────────────────────────────────────────────────────────────────────
    @guarded("roadsafety_triage")
    def roadsafety_triage(question: str):
        return one("triage", "card", question=question)

    return [
        ToolDef("roadsafety_orient",
                "Start here. section=about: is this the CBS road-accidents database, coverage (data end 2024-12-31), "
                "row counts per series, the golden rules, the deployed models. section=models: the model registry "
                "(family site|severity) with gate verdicts. section=trap: the naive 'light accidents' count vs the "
                "correct one for a year (the damage-only series inflates it ~9x). section=catalog: every tool and "
                "the actions behind it.", roadsafety_orient),
        ToolDef("roadsafety_trend",
                "Counts over time from the casualty series: accidents, fatal_accidents (events) or killed / "
                "severe_injured / slight_injured (people), by year or month, all roads or urban/nonurban, 2005-2024. "
                "Counts, not risk (no exposure denominator); missing person-level years show as gaps. face=table "
                "for the rows, face=sql for the exact statement.", roadsafety_trend),
        ToolDef("roadsafety_breakdown",
                "Casualties by ONE dimension (casualty_type, road_type, day_night, age_group, weather, "
                "involved_vehicle_type, sex, lighting, hour_of_day, day_of_week, speed_limit, road_shape, year) as "
                "shares — by=year with display=counts gives the three severity lines over time (the share-drift "
                "exhibit). by=day_hour: the 7x24 casualty-accident grid. by=weather_vs_measured: the officer's "
                "weather label against ERA5 measured rain. Relative to being a casualty — not risk.",
                roadsafety_breakdown),
        ToolDef("roadsafety_sites",
                "Where is it dangerous. rank_by=excess: Empirical-Bayes screening against the DEPLOYED site model "
                "(observed minus expected, NB 90% interval) — the honest ranking, segments only, 2017-2024. "
                "rank_by=rate: casualty accidents per 100M vehicle-km per interurban segment with a Poisson CI. "
                "rank_by=observed: raw counts per unit (segments | njunctions | ujunctions) — counts are not risk. "
                "rank_by=zones / cities: traffic-analysis zones or municipalities from the CUMULATIVE undated "
                "snapshot (per_capita | density | ped_share; total for cities) — a separate universe, never compare "
                "with the yearly series. road=0 means all roads.", roadsafety_sites),
        ToolDef("roadsafety_site",
                "One site, everything that can honestly be said: yearly observed strip (counts, severity, day/night); "
                "model measures (expected, excess, EB, interval) for ROAD segments only — junctions have no exposure "
                "denominator and never get rates; a relative severity profile when a severity model is deployed. "
                "site = '60/836' (road/segment), 'road:60/96.0-98.8' (km range), 'njunction:<code>' or "
                "'ujunction:<city>/<code>'. drivers=true appends the SHAP per-site drivers card (segments).",
                roadsafety_site),
        ToolDef("roadsafety_change_effect",
                "Did a change at a site work. mode=evaluate: double difference-in-differences for one site around "
                "change_year (casualty series and damage-only series, each against the national network; the change "
                "year excluded; window_years 1-3; thin cells give n/a). mode=discover: scan every traffic-count "
                "segment for change points ranked by |z| — a rank score only, then confirm the candidate with "
                "mode=evaluate. Association, not proof.", roadsafety_change_effect),
        ToolDef("roadsafety_vehicles",
                "Vehicle risk. kind=cells: Empirical-Bayes involvement rate per (manufacture year x engine band) over "
                "real vehicle-km exposure, three tiers; kind=cohort: one row per manufacture year. metric involvements "
                "| ksi | fatal; bands=known_engine drops the unknown-engine (EV) band. kind=two_wheelers: motorcycle "
                "involvements per 1,000 active vehicles by cc band (2013+), bicycles/e-bikes/e-scooters as counts only. "
                "Cells, never makes or models — the files carry no plate or model code.", roadsafety_vehicles),
        ToolDef("roadsafety_predict",
                "The DEPLOYED severity model on one risk profile (road_type, time, casualty, age, safety, speed — "
                "leave a field 'לא צוין' to keep it honestly unspecified): predicted killed/severe/slight "
                "distribution RELATIVE to the holdout baseline, with the SHAP waterfall. Set switch (e.g. 'חגור "
                "לעומת לא חגור') for the what-if pair: baseline vs the flipped scenario and the relative deltas. "
                "Association, not intervention. Refuses without a deployed severity model.", roadsafety_predict),
        ToolDef("roadsafety_explain",
                "How the models decide. family=severity: SHAP beeswarm over the person matrix for severity_class "
                "(הרוג | פצוע קשה), or the dependence view of one feature; sample 20k (seconds) | 50k | full "
                "(~340k rows, up to a minute). family=site: TreeSHAP drivers of the site model — global profile "
                "(site='') or one segment (site='60/836'); style פרופיל | נחיל. face=card for the plain-Hebrew "
                "drivers card.", roadsafety_explain),
        ToolDef("roadsafety_studio",
                "The model lifecycle (needs xgboost). op=validate (read-scored, safe): the gate on model_id or "
                "'latest' — site: Spearman >= 0.3 and calibration within 25%; severity: fatal recall >= 0.5, AUC >= "
                "0.8, overfit gap <= 0.05. op=train and op=deploy CHANGE SHARED STATE: when the client supports "
                "elicitation the server itself asks the person through a confirmation form (confirm is then "
                "ignored); otherwise they are refused unless confirm=true — ask the person first, then call again "
                "with confirm=true. train: family site (train_until 2018-2023, features doc-11 | shuffled) or "
                "severity (person-12 | shuffled). deploy: only a VALIDATED model.",
                roadsafety_studio, read_only=False),
        ToolDef("roadsafety_finding",
                "The findings ledger — every TOOL RUN that answered (answers AND refusals) with its headline numbers; "
                "chat messages are not in it. op=list shows the last_n entries with their idx; op=card promotes ONE "
                "LEDGER ENTRY — entry='latest' (the most recent tool run) or an idx from the list — to a finding card "
                "with the claim, the evidence numbers, the caveats and the exact rerun recipe. To card a specific "
                "answer, pass its idx.", roadsafety_finding),
        ToolDef("roadsafety_triage",
                "Ask this FIRST when unsure whether the database can answer: a rule-based gate (no LLM) that names "
                "what cannot be answered (make/model safety, per-km risk in cities or at junctions, dates after "
                "2024-12-31, residence as location) with the reason and what IS answerable, or routes the question "
                "to the fitting instruments.", roadsafety_triage),
        ToolDef("roadsafety_find",
                "Find a site by NAME and get the key the other tools take. Searches interurban segment names "
                "(traffic_segments), non-urban junction names (e.g. 'צומת העשור' → njunction:433), urban junctions "
                "by street or city name (→ ujunction:<city>/<code>) and settlements (dim_settlement). Use it before "
                "roadsafety_site / roadsafety_change_effect when the person names a place rather than a code. "
                "Partial names work; kind narrows the search; limit up to 25 per kind.", roadsafety_find),
    ]


def mapped_actions() -> set[str]:
    return {a for actions in TOOL_ACTIONS.values() for a in actions}


class ConfirmSchema:
    """Built lazily: pydantic is an SDK dependency, and this module must import without the SDK."""
    _model = None

    @classmethod
    def model(cls):
        if cls._model is None:
            from pydantic import BaseModel, Field

            class Confirm(BaseModel):
                approve: bool = Field(description="true = run it; false = do nothing")
            cls._model = Confirm
        return cls._model


async def hard_gate(ctx, op: str, family: str, **details) -> str:
    """M2: the hard confirmation gate. When the connected client advertises elicitation (Claude Code does; Claude
    Desktop and claude.ai do not, as of 2026-10), the SERVER asks the person through a form and proceeds only on an
    explicit accept — a headless or over-eager model cannot set a flag to get past it. Returns "accepted",
    "declined" or "unavailable" (no client capability → the caller falls back to the confirm flag)."""
    if ctx is None:
        return "unavailable"
    try:
        caps = ctx.client_capabilities
        if caps is None or getattr(caps, "elicitation", None) is None:
            return "unavailable"
    except Exception:  # noqa: BLE001 — no request in flight (direct calls in tests/scripts)
        return "unavailable"
    what = {"train": "אימון מודל", "deploy": "פריסת מודל"}[op]
    detail = ", ".join(f"{k}={v}" for k, v in details.items() if v not in (None, "", "default"))
    message = (f"{what} ({family}{', ' + detail if detail else ''}) ישנה את המצב המשותף של המעבדה "
               f"(רישום המודלים תחת תיקיית הנתונים). לאשר?")
    result = await ctx.elicit(message, ConfirmSchema.model())
    if getattr(result, "action", "") == "accept" and getattr(getattr(result, "data", None), "approve", False):
        return "accepted"
    return "declined"
