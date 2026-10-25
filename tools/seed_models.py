# -*- coding: utf-8 -*-
"""Seed the model registry: train -> validate -> deploy the two reference models every number in the docs
assumes (site: trained through 2023, doc-11 features, seed 42; severity: through 2022, person-12, seed 42).

    app\\.venv\\Scripts\\python nl2sql-roadsafety-lab\\tools\\seed_models.py [--db PATH] [--family site|severity|both] [--force]

Runs the plugin's own studio actions IN-PROCESS through the engine's Registry (exactly what the page and the MCP
server do) - the app need not be running. Writes only under the shared data dir (NL2SQL_CORE_DATA_DIR, else
%LOCALAPPDATA%\\nl2sql-core): accidents/models/<family>/<model_id>/ plus one ledger line per action, like any
run from the page. Idempotent: a family that already has a deployed model is skipped unless --force.
Exit 0 = both families deployed (or already were); 1 = a gate rejected or a step failed; 2 = cannot start."""
from __future__ import annotations

import argparse
import sys
import time

FAMILIES = (
    # family, training action, validation action
    ("site", "studio_train_site", "studio_validate"),
    ("severity", "studio_train_severity", "studio_validate_severity"),
)
REFUSAL_MARK = "# ❌"      # the envelope's refusal card opens with "# ❌"


def _text(result) -> str:
    data = result.data
    return data if isinstance(data, str) else str(data)[:600]


def _failed(result) -> bool:
    """An error Result, or a refusal card (the envelope's markdown refusal face)."""
    if result.kind == "error":
        return True
    return isinstance(result.data, str) and result.data.lstrip().startswith(REFUSAL_MARK)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="seed_models", description=__doc__.split("\n\n")[0])
    p.add_argument("--db", default=None,
                   help="israel_accidents.duckdb (else $NL2SQL_ROADSAFETY_DB, else the default working copy)")
    p.add_argument("--family", choices=("site", "severity", "both"), default="both")
    p.add_argument("--force", action="store_true",
                   help="train again even when the family already has a deployed model")
    a = p.parse_args(argv)

    try:
        from nl2sql_roadsafety.mcp.runner import Runner, resolve_db_path
        from nl2sql_roadsafety.studio import registry
    except ImportError as exc:  # the plugin is not in this interpreter
        print("cannot import the plugin (%s) - run install-plugin.bat first, and use the app's .venv python" % exc)
        return 2
    try:
        import xgboost  # noqa: F401  (the [ml] tier)
    except ImportError:
        print("xgboost is not installed in the app's environment - re-run install-plugin.bat with internet (the ml tier)")
        return 2

    db = resolve_db_path(a.db)
    runner = Runner(db, audit_enabled=False)      # not a chat call: no MCP audit line
    missing = runner.db_missing()
    if missing:
        print(missing)
        return 2
    ctx = runner.ctx
    print("database : %s" % db)
    print("data dir : %s" % ctx.data_dir())

    rc = 0
    for family, train_action, validate_action in FAMILIES:
        if a.family not in ("both", family):
            continue
        pointer, meta = registry.deployed(ctx, family)
        if pointer and meta and not a.force:
            print("[%s] already deployed: %s - skipped (--force trains again)" % (family, meta.get("model_id")))
            continue

        before = {m.get("model_id") for m in registry.list_models(ctx, family)}
        print("[%s] training (%s, defaults) ..." % (family, train_action), flush=True)
        t0 = time.perf_counter()
        step = runner.run(train_action)
        if _failed(step.result):
            print("[%s] training failed:\n%s" % (family, _text(step.result)))
            rc = 1
            continue
        new = [m for m in registry.list_models(ctx, family) if m.get("model_id") not in before]
        if not new:
            print("[%s] training returned but no new registry entry appeared:\n%s" % (family, _text(step.result)))
            rc = 1
            continue
        model_id = new[-1]["model_id"]
        print("[%s] trained %s in %.0f s" % (family, model_id, time.perf_counter() - t0))

        print("[%s] validating (%s) ..." % (family, validate_action), flush=True)
        step = runner.run(validate_action, model_id=model_id)
        meta = registry.read_meta(ctx, model_id, family) or {}
        gate = meta.get("gate") or {}
        print("[%s] gate verdict: %s - metrics %s" % (family, meta.get("status"), gate.get("metrics")))
        if meta.get("status") != "validated":
            print("[%s] the gate did not validate the model: %s" % (family, gate.get("reasons") or _text(step.result)))
            rc = 1
            continue

        step = runner.run("studio_deploy", model_id=model_id, family=family)
        pointer, meta = registry.deployed(ctx, family)
        if pointer and pointer.get("model_id") == model_id:
            print("[%s] deployed %s" % (family, model_id))
        else:
            print("[%s] deploy did not take:\n%s" % (family, _text(step.result)))
            rc = 1

    for family, _, _ in FAMILIES:
        pointer, meta = registry.deployed(ctx, family)
        print("deployed %-8s: %s" % (family, (pointer or {}).get("model_id") or "-"))
    print("done" if rc == 0 else "finished with problems - see above")
    return rc


if __name__ == "__main__":
    sys.exit(main())
