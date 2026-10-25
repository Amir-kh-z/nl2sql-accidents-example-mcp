# -*- coding: utf-8 -*-
"""nl2sql-roadsafety-lab — מעבדת הבטיחות בדרכים (Road Safety Lab).

Correct-by-construction actions over the Israel road-accidents database (CBS) for the NL2SQL
closed-core app. The app's discover() runs on every request, so this module stays light: the
action modules import only the standard library, the engine contract and their siblings; matplotlib
is imported inside the chart path only.
"""
__version__ = "0.14.3"         # defined BEFORE the action imports (envelope.version() falls back to it)

from nl2sql_engine.modules import Module

from .actions import (ab_scan, about, before_after, city_ranking, finding_card, heat_matrix, hotspot_map,
                      ledger_list, map_scene, segment_rates, severity_explain, severity_predict, severity_profile,
                      site_profile, site_ranking, studio_deploy, studio_explain, studio_models,
                      studio_train_severity, studio_train_site, studio_validate, studio_validate_severity,
                      trap, trend, triage, two_wheelers, vehicle_cells, weather_check, what_if, zone_ranking)

MODULE = Module(
    name="roadsafety",
    label="🚦 מעבדת הבטיחות בדרכים · Road Safety Lab",
    description="Road Safety Lab over the Israel road-accidents database (CBS). Every answer carries "
                "its series filter, join key, denominator, caveats and CBS credit — correct by "
                "construction; it refuses, readably, what the data cannot answer.",
    requires_core=">=1.0,<2.0",
    actions=[trend.ACTION, trap.ACTION, about.ACTION, segment_rates.ACTION, hotspot_map.ACTION, map_scene.ACTION,
             site_profile.ACTION, site_ranking.ACTION,
             severity_profile.ACTION, vehicle_cells.ACTION, two_wheelers.ACTION, before_after.ACTION,
             ab_scan.ACTION, weather_check.ACTION, heat_matrix.ACTION, zone_ranking.ACTION, city_ranking.ACTION,
             severity_predict.ACTION, what_if.ACTION, severity_explain.ACTION,
             studio_train_site.ACTION,
             studio_validate.ACTION, studio_train_severity.ACTION, studio_validate_severity.ACTION,
             studio_deploy.ACTION, studio_explain.ACTION, studio_models.ACTION, ledger_list.ACTION,
             finding_card.ACTION, triage.ACTION],
)
