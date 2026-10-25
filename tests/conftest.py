# -*- coding: utf-8 -*-
"""One small hand-planted DuckDB (no RNG, no CBS data) that mirrors the accidents schema the actions
touch — with the traps planted on purpose: accident IDs that COLLIDE across the two series, a killed
person in the damage-only series, a period whose person-level rows are fewer than its accidents (the
coverage rule fires), months with zero events (zero-fill), a road code the live data never carries,
overlapping traffic-segment vintages (the units CTE), a boundary km the half-open predicate excludes,
an accident matching two segments (QUALIFY), a pedestrian who carries a vehicle code, Excel-mangled and
NULL age labels, a negative and a NULL road_km, a duplicated junction code, a band-0 and zero-exposure
vehicle cells, weather rows around the 0.1 mm threshold, and (P13) deterministic accident-attribute
columns: day_of_week off the real calendar, ONE unknown-hour/lighting row (the weather-9 row A5),
speed-limit sentinel 0 on the off-road row, road-shape code 9 'אחר' on rt-3 rows, and (P14) the
cumulative geographic snapshot (accidents_by_taz / accidents_by_municipality / dim_settlement) with a
zero-population zone, a through-traffic zone, a city code missing from the settlement dictionary and
accident_index planted exactly equal to the density.

P1 rows live in 2022–2024; P2 rows in 2012–2021 — every P1 expectation stays."""
from __future__ import annotations

import datetime as dt

import pytest

import nl2sql_engine
from nl2sql_engine.modules import Context

SEV = {1: "קטלנית", 2: "קשה", 3: "קלה"}
ROAD = {1: "עירונית בצומת", 2: "עירונית לא בצומת", 3: "לא-עירונית בצומת", 4: "לא-עירונית לא בצומת", 5: "שטח"}
INJ = {0: "לא נפגע", 1: "הרוג", 2: "פצוע קשה", 3: "פצוע קל"}
WEATHER = {1: "בהיר", 2: "גשום", 9: "לא ידוע"}
DAYNIGHT = {1: "יום", 5: "לילה"}
# P13 accident-attribute dims (severity_profile + heat_matrix) — deterministic rules in _acc_row, no RNG
DOW = {1: "ראשון", 2: "שני", 3: "שלישי", 4: "רביעי", 5: "חמישי", 6: "שישי", 7: "שבת"}
LIGHT = {1: "אור יום רגיל", 3: "לילה פעלה תאורה"}
SPEED = {0: "לא ידוע", 1: 'עד 50 קמ"ש', 4: '80 קמ"ש'}          # 0 = the live sentinel (never dropped)
SHAPE = {5: "עקום חד", 8: "כביש ישר / צומת", 9: "אחר"}          # 9 = the 2011 coding-change trap
CTYPE = {1: "הולך רגל", 2: "נהג - רכב בעל 4 גלגלים ויותר", 3: "נוסע - רכב בעל 4 גלגלים ויותר",
         4: "נהג - אופנוע", 6: "נהג - אופניים"}
VTYPE = {1: "רכב נוסעים פרטי", 2: "משא עד 3.5 טון - אחוד (טרנזיט)", 3: "משא עד 3.5  טון - לא אחוד (טנדר)",
         9: 'אופנוע 51 עד 125 סמ"ק', 10: 'אופנוע 126 עד 400 סמ"ק', 11: "אוטובוס", 12: "מונית", 15: "אופניים"}
SEX = {1: "זכר", 2: "נקבה"}
CITY = {5000: "תל אביב - יפו"}

# ── P1 rows (2022–2024): id, year, month, severity, road_type, involved injury codes ──
P1_CASUALTY = [
    (2024000001, 2024, 1, 1, 1, [1, 1, 3, 0]),
    (2024000002, 2024, 1, 3, 2, [3, 0]),
    (2024000003, 2024, 2, 2, 3, [2, 3]),
    (2024000004, 2024, 3, 3, 4, [3]),
    (2024000005, 2024, 3, 3, 4, [3, 0]),
    (2024000006, 2024, 5, 3, 5, [3]),          # road code 5: a guard for a code the live data never has
    (2023000001, 2023, 6, 1, 4, [1, 0]),
    (2023000002, 2023, 7, 3, 1, [3]),
    (2022000001, 2022, 12, 2, 2, []),          # no person rows → coverage rule fires for 2022
    (2022000002, 2022, 11, 3, 4, [0]),
]
P1_DAMAGE = ([(2024000000 + i, 2024, ((i - 1) % 12) + 1, 2 if i <= 15 else 4) for i in range(1, 21)]
             + [(2023000000 + i, 2023, i, 2) for i in range(1, 5)]
             + [(2022000000 + i, 2022, i, 4) for i in range(1, 6)])
P1_DAMAGE_INVOLVED = [(2024000001, 1, 3, 2024, 1, 1), (2024000001, 2, 3, 2024, 1, 0), (2024000002, 1, 3, 2024, 2, 0)]
VEHICLES = [(2024000001, 1, 2024, 1, None), (2024000001, 1, 2024, 2, None),
            # P5 two_wheelers: TYPED rows on EXISTING accidents only (no pinned aggregate moves).
            # band 9 (fleet 1,000): 2019 S1+S2 (S2 fatal) → 2.0/1000, 2020 S4+S5+S6 → 3.0, 2021 S8 (fatal) → 1.0
            (2019000001, 1, 2019, 1, 9), (2019000002, 1, 2019, 1, 9),
            (2020000001, 1, 2020, 1, 9), (2020000002, 1, 2020, 1, 9), (2020000003, 1, 2020, 1, 9),
            (2021000002, 1, 2021, 1, 9),
            # band 19 (fleet 500): 2019 S3 → 2.0, 2021 S7 → 2.0; bands 8/10 have fleet but zero accidents
            (2019000003, 1, 2019, 1, 19), (2021000001, 1, 2021, 1, 19),
            # counts-only: 15 bicycle (Z1 2019, S10 2021), 23 e-bike (a SECOND vehicle on S5), 21 e-scooter (S9)
            (2019000005, 1, 2019, 1, 15), (2021000003, 1, 2021, 1, 15),
            (2020000002, 1, 2020, 2, 23), (2019000004, 1, 2019, 1, 21),
            # traps: a damage-series motorcycle (case 3 — the composite filter must drop it) and a 2012 one (pre-era)
            (2024000001, 3, 2024, 1, 9), (2012000003, 1, 2012, 1, 9)]
FLEET_MOTORCYCLES = [   # make, model, manufacture_year, band_code, band, active — a CURRENT snapshot, like live
    ("יצרן א", "דגם א", 2018, 9, 'אופנוע 51 עד 125 סמ"ק', 600),
    ("יצרן א", "דגם ב", 2020, 9, 'אופנוע 51 עד 125 סמ"ק', 400),
    ("יצרן ב", "דגם ג", 2019, 19, 'אופנוע 401+ סמ"ק', 500),
    ("יצרן ג", "דגם ד", 2015, 8, 'אופנוע עד 50 סמ"ק', 200),
    ("יצרן ג", "דגם ה", 2016, 10, 'אופנוע 126 עד 400 סמ"ק', 300),
]

# ── P2 casualty rows (2012–2021):
# (id, year, month, sev, road_type, road1_number, road_km, nu_junction, u_junction, city, weather, day_night, cell,
#  involved [(injury, casualty_type, age_group, age_label, vehicle_type, sex)])
P2_CASUALTY = [
    ("A1", 2012000001, 2012, 1, 3, 4, 1, 10, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),
    ("A2", 2012000002, 2012, 2, 2, 4, 1, 20, 0, 0, 0, 2, 5, 1, [(2, 3, 6, "25-29", 1, 2)]),
    ("A3", 2012000003, 2012, 3, 3, 4, 1, 30, 0, 0, 0, 1, 1, 1, [(3, 4, 5, "20-24", 9, 1)]),
    ("A4", 2013000001, 2013, 1, 1, 4, 1, 40, 0, 0, 0, 1, 1, 1, [(1, 1, 17, "80-84", None, 2)]),
    ("A5", 2013000002, 2013, 2, 3, 4, 1, 50, 0, 0, 0, 9, 1, 1, [(3, 2, 2, "05-ספטמבר", 1, 1)]),   # Excel-mangled label
    ("A6", 2013000003, 2013, 3, 3, 4, 1, 60, 0, 0, 0, 1, 5, None, [(3, 2, 7, None, 2, 1)]),       # no weather cell, NULL label
    ("A7", 2014000001, 2014, 1, 2, 4, 1, 70, 0, 0, 0, 2, 1, 1, [(2, 1, 99, "לא ידוע", 1, 1)]),   # pedestrian WITH a vehicle code
    ("A8", 2014000002, 2014, 2, 3, 4, 1, 80, 0, 0, 0, 1, 1, 1, [(3, 3, 10, "45-49", 1, 2), (0, 2, 8, "35-39", 1, 1)]),
    ("A9", 2016000001, 2016, 1, 3, 4, 1, 90, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),
    ("S11", 2018000001, 2018, 6, 3, 4, 1, 30, 0, 0, 0, 1, 1, 1, [(3, 2, 6, "25-29", 1, 1)]),
    ("B1", 2012000004, 2012, 5, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 5, "20-24", 1, 1)]),
    ("B2", 2012000005, 2012, 6, 3, 1, None, None, 0, 777, 5000, 1, 1, 2, [(3, 1, 3, "אוקטובר-14", None, 1)]),
    ("B3", 2012000006, 2012, 7, 2, 3, 9, 500, 433, 0, 0, 2, 5, 2, [(2, 4, 5, "20-24", 10, 1)]),
    ("B4", 2013000004, 2013, 5, 3, 1, None, None, 0, 777, 5000, 1, 1, 2, [(3, 3, 12, "55-59", 1, 2)]),
    ("B5", 2013000005, 2013, 6, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 9, "40-44", 3, 1)]),
    ("B6", 2013000006, 2013, 7, 1, 2, None, None, 0, 0, 5000, 1, 1, 2, [(1, 1, 18, "85+", None, 2), (3, 2, 4, "15-19", 1, 1)]),
    ("B7", 2014000003, 2014, 5, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 5, "20-24", 1, 1)]),
    ("B8", 2014000004, 2014, 6, 3, 1, None, None, 0, 777, 5000, 1, 1, 2, [(3, 6, 4, "15-19", 15, 1)]),
    ("B9", 2016000002, 2016, 5, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 5, "20-24", 1, 1)]),
    ("B10", 2016000003, 2016, 6, 2, 1, None, None, 0, 777, 5000, 1, 1, 2, [(2, 1, 1, "00-04", None, 1)]),
    ("B11", 2017000001, 2017, 5, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 6, "25-29", 1, 2)]),
    ("B12", 2017000002, 2017, 6, 3, 2, None, None, 0, 0, 5000, 1, 1, 2, [(3, 2, 7, "30-34", 12, 1)]),
    ("B13", 2018000002, 2018, 5, 3, 3, 9, 500, 433, 0, 0, 1, 1, 2, [(3, 2, 5, "20-24", 1, 1)]),
    ("B14", 2018000003, 2018, 7, 3, 1, None, None, 0, 777, 5000, 1, 1, 2, [(3, 3, 11, "50-54", 11, 2)]),
    ("S1", 2019000001, 2019, 1, 3, 4, 1, 20, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),
    ("S2", 2019000002, 2019, 2, 1, 4, 1, 98, 0, 0, 0, 1, 1, 1, [(1, 2, 5, "20-24", 1, 1)]),      # km 9.8: segments 10 AND 11 → QUALIFY
    ("S3", 2019000003, 2019, 3, 2, 4, 1, 120, 0, 0, 0, 1, 1, 1, [(2, 2, 5, "20-24", 1, 1)]),     # km 12.0 → segment 11
    ("S9", 2019000004, 2019, 4, 3, 4, 1, None, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),    # NULL km
    ("S4", 2020000001, 2020, 1, 3, 4, 1, 110, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),     # km 11.0: only the discarded vintage
    ("S5", 2020000002, 2020, 2, 3, 4, 1, 50, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),
    ("S6", 2020000003, 2020, 3, 2, 4, 2, 60, 0, 0, 0, 1, 1, 1, [(2, 3, 6, "25-29", 1, 2)]),
    ("S7", 2021000001, 2021, 1, 3, 4, 2, 75, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),      # km 7.5: half-open boundary → unmatched
    ("S8", 2021000002, 2021, 2, 1, 4, 2, 74, 0, 0, 0, 1, 1, 1, [(1, 4, 5, "20-24", 9, 1)]),
    ("S10", 2021000003, 2021, 3, 3, 4, 1, -5, 0, 0, 0, 1, 1, 1, [(3, 2, 5, "20-24", 1, 1)]),     # negative km
    ("Z1", 2019000005, 2019, 8, 3, 1, None, None, 0, 99999999, 5000, 1, 1, None, [(3, 2, 5, "20-24", 1, 1)]),   # sentinel junction code, no cell (outside the before/after windows)
]
# P2 damage-only rows per year: the site rows (ids collide with the A-ids) and the junction rows
# (road_km NULL in 2017 and 2018 → the coding-share flag)
P2_DAMAGE_YEARS = (2012, 2013, 2014, 2016, 2017, 2018)

TRAFFIC_ADT_ASOF = [   # road, seg, km_from, km_to, year, adt_asof, based_on_year, gap_years
    (1, 10, 0.0, 10.0, 2019, 10000.0, 2019, 0),
    (1, 10, 0.0, 10.0, 2020, 10000.0, 2020, 0),
    (1, 10, 0.0, 12.0, 2020, 12000.0, 2018, 2),      # overlapping vintage — the units CTE discards it
    (1, 10, 0.0, 10.0, 2021, 10000.0, 2021, 0),
    (1, 11, 9.5, 15.0, 2019, 5000.0, 2018, 1),
    (2, 20, 5.0, 7.5, 2020, 20000.0, 2020, 0),
    (2, 20, 5.0, 7.5, 2021, 20000.0, 2021, 0),
]
TRAFFIC_SEGMENTS = [   # road, seg, km_from, km_to, name_from, name_to, src_year
    (1, 10, 0.0, 10.0, "צומת א", "צומת ב", 2019),
    (1, 10, 0.0, 12.0, "צומת א", "צומת ב", 2020),   # second vintage → any_value
    (1, 11, 9.5, 15.0, "צומת ב", "צומת ה", 2019),
    (2, 20, 5.0, 7.5, "מחלף ג", "צומת ד", 2020),
]
VEHICLE_CELLS = [   # manufacture_year, cc_band, exposure_mkm, involvements, ksi, fatal  (fleet 10,000 each)
    (2016, 5, 1000.0, 400, 40, 4), (2016, 6, 4000.0, 800, 80, 8), (2017, 6, 4000.0, 600, 60, 6),
    (2018, 6, 2000.0, 500, 50, 5), (2019, 0, 50.0, 40, 4, 1), (2019, 8, 1000.0, 100, 10, 1),
    (2020, 6, 2000.0, 300, 30, 3), (2021, 9, 500.0, 350, 35, 4), (2022, 6, 1000.0, 50, 5, 0),
    (2023, 4, 200.0, 10, 1, 0),
]
ZERO_EXPOSURE_CELLS = [(2025, 6, 1000), (2026, 0, 500)]     # manufacture_year, cc_band, fleet
WEATHER_SPECIAL = {"A2": (2.0, 12.0), "A7": (0.5, 14.0), "B3": (0.05, 16.0), "A5": (0.3, 18.0),
                   "A8": (1.0, 20.0), "S4": (0.05, 30.0)}   # precipitation_mm, temperature_c
NO_GEO = {"S3"}                                            # a weather cell but no coordinates (the live 0.4 %)
SWAPPED_STREETS = {"B8", "B14"}                            # the same junction with its two streets recorded in the other order
# P2_CASUALTY's last row "Z1" (2019, urban, no weather cell) is an "unknown junction" sentinel (urban_junction_code
# 99999999, live: 556 casualty accidents in 82 cities) — it must never rank on the map, count as coded, or parse as a
# site; it IS a casualty accident everywhere else (about, severity_profile, weather coverage)

# P14 geographic snapshot fixture (a separate universe by design — no year axis anywhere): accident_index is
# planted EXACTLY equal to the density (accidents per km2, taz_area in SQUARE METERS) so corr(index, density)
# pins at 1.000 while the per-capita ORDER differs (density top = zone 102, per-capita top = zone 104);
# zone 102 is the through-traffic trap (200 residents, 45 accidents — min_pop 500 removes it), zone 103 has
# zero population, city 8888 is missing from dim_settlement (the 'קוד' fallback in zone AND city labels),
# zone 106 / city 8888 have no injured at all (the ped_share guard). Zones 105/106 tie on density 10.0
# (the label tie-break) and 104/105 tie on ped_share 40.0.
TAZ_ZONES = [   # taz, city, pop2018, land_use, area_m2, accidents, killed, severe, slight, ped, ev,
                # inj_0_19, inj_20_64, inj_65p, injured_total
    (101, 5000, 2000, 1, 1_000_000.0, 40, 1, 4, 15, 5, 1, 4, 12, 4, 20),
    (102, 5000,  200, 2,   500_000.0, 45, 0, 6, 24, 9, 2, 6, 20, 4, 30),
    (103, 6100,    0, 3, 2_000_000.0, 12, 0, 2,  6, 0, 0, 1,  6, 1,  8),
    (104, 8888, 1000, 1, 4_000_000.0, 30, 2, 3, 10, 6, 0, 3,  9, 3, 15),
    (105, 7100, 5000, 4, 2_500_000.0, 25, 1, 5, 19, 10, 1, 5, 15, 5, 25),
    (106, 7100,  800, 5,   800_000.0,  8, 0, 0,  0, 0, 0, 0,  0, 0,  0),
]
MUNICIPALITIES = [   # city, municipal_code, area_sqkm (ALREADY km2), accidents, killed, severe, slight, ped, injured_total
    (5000, 1, 52.0, 400, 5, 40, 255, 60, 300),
    (6100, 2,  7.0, 140, 1, 12,  87, 30, 100),
    (7100, 3, 50.0, 100, 2, 10,  68, 10,  80),
    (8888, 4, 10.0,  50, 0,  0,   0,  0,   0),
]
SETTLEMENTS = [   # city_code, name_he, name_en, region_code, region_name, regional_council_name
    (5000, "תל אביב - יפו", "Tel Aviv-Yafo", 51, "תל אביב", None),
    (6100, "בני ברק", "Bnei Brak", 52, "רמת גן", None),
    (7100, "אשקלון", "Ashkelon", 61, "אשקלון", None),
    (9999, "יישוב ללא תאונות", None, 62, "באר שבע", "מועצה כלשהי"),    # a dim row with no snapshot row
]

CODE_LOOKUPS = [   # code_table, code, year, label_he, field — a small slice of the live dictionary
    (30, 1, 2024, "הולך רגל", "casualty_type_code"), (30, 4, 2024, "רוכב אופנוע", "casualty_type_code"),
    (14, 1, 2024, "חגורת בטיחות", "safety_equipment_code"), (14, 4, 2024, "לא השתמש באמצעי", "safety_equipment_code"),
    (5, 1, 2024, "עירונית בצומת", "road_type_code"), (5, 4, 2024, "לא-עירונית לא בצומת", "road_type_code"),
    (18, 1, 2024, "יום", "day_night_code"), (18, 5, 2024, "לילה", "day_night_code"),
    (18, 5, 2010, "שעות החשכה", "day_night_code"),                    # older label → arg_max must prefer 2024
    (12, 8, 2024, "אופנוע עד חמישים", "vehicle_type_code"),           # involved_vehicle_type_code decodes here
    (9, 1, 2024, "זכר", "sex_code"), (9, 2, 2024, "נקבה", "sex_code"),
]

DDL = """
CREATE TABLE accidents (accident_id BIGINT, case_type_code SMALLINT, year SMALLINT, month SMALLINT,
    accident_date DATE, severity_code SMALLINT, severity_label VARCHAR, road_type_code SMALLINT, road_type_label VARCHAR,
    road1_number INTEGER, road_km DOUBLE, nonurban_junction_code INTEGER, nonurban_junction_name VARCHAR,
    urban_junction_code INTEGER, city_code INTEGER, city_name VARCHAR, street1_name VARCHAR, street2_name VARCHAR,
    weather_code SMALLINT, weather_label VARCHAR, day_night_code SMALLINT, day_night_label VARCHAR,
    hour_of_day SMALLINT, accident_timestamp TIMESTAMP, weather_cell_id INTEGER, latitude DOUBLE, longitude DOUBLE,
    road_surface_label VARCHAR, road_shape_code SMALLINT, single_carriageway_code SMALLINT,
    dual_carriageway_code SMALLINT, road_surface_code SMALLINT, speed_limit_code SMALLINT);
CREATE TABLE involved (accident_id BIGINT, vehicle_num SMALLINT, person_id INTEGER, case_type_code SMALLINT,
    year SMALLINT, month SMALLINT, injury_severity_code SMALLINT, injury_severity_label VARCHAR,
    casualty_type_code SMALLINT, casualty_type_label VARCHAR, age_group_code SMALLINT, age_group_label VARCHAR,
    involved_vehicle_type_code SMALLINT, involved_vehicle_type_label VARCHAR, sex_code SMALLINT, sex_label VARCHAR,
    safety_equipment_code SMALLINT, population_group_code SMALLINT);
CREATE TABLE vehicles (accident_id BIGINT, case_type_code SMALLINT, year SMALLINT, vehicle_num SMALLINT,
    vehicle_type_code SMALLINT);
CREATE TABLE fleet_motorcycles (make VARCHAR, model VARCHAR, manufacture_year SMALLINT,
    engine_cc_band_code SMALLINT, engine_cc_band VARCHAR, active INTEGER);
CREATE TABLE traffic_adt_asof (road DOUBLE, seg DOUBLE, km_from DOUBLE, km_to DOUBLE, year BIGINT,
    adt_asof DOUBLE, based_on_year BIGINT, gap_years BIGINT);
CREATE TABLE traffic_segments (road BIGINT, seg BIGINT, km_from DOUBLE, km_to DOUBLE, name_from VARCHAR,
    name_to VARCHAR, placement VARCHAR, technology VARCHAR, src_year BIGINT, loaded_at TIMESTAMP);
CREATE TABLE vehicle_cells (manufacture_year BIGINT, cc_band BIGINT, fleet BIGINT, mean_weight_kg DOUBLE,
    ev_share DOUBLE, mean_annual_km DOUBLE, km_measured BIGINT, years_exposed BIGINT, exposure_mkm DOUBLE,
    involvements BIGINT, ksi_involvements BIGINT, fatal_involvements BIGINT);
CREATE TABLE dim_junction_nonurban (junction_code INTEGER, road1_number INTEGER, road2_number INTEGER,
    road_km DOUBLE, junction_name VARCHAR, x_itm DOUBLE, y_itm DOUBLE, latitude DOUBLE, longitude DOUBLE);
CREATE TABLE dim_junction_urban (junction_code INTEGER, city_code INTEGER, street1_code INTEGER,
    street2_code INTEGER, x_itm DOUBLE, y_itm DOUBLE, latitude DOUBLE, longitude DOUBLE);
CREATE TABLE weather_hourly (cell_id INTEGER, observed_at TIMESTAMP, temperature_c DOUBLE, precipitation_mm DOUBLE,
    humidity_pct DOUBLE, wind_speed_kmh DOUBLE, weather_code INTEGER);
CREATE TABLE code_lookups (code_table INTEGER, code INTEGER, year SMALLINT, label_he VARCHAR, field VARCHAR);
CREATE TABLE dim_weather_code (weather_code INTEGER, description_en VARCHAR, description_he VARCHAR);
CREATE TABLE accidents_by_taz (taz_object_id INTEGER, city_code INTEGER, population_2018 INTEGER,
    land_use_code INTEGER, taz_area DOUBLE, total_accidents INTEGER, killed INTEGER, severely_injured INTEGER,
    slightly_injured INTEGER, pedestrians_injured INTEGER, electric_vehicle_injured INTEGER,
    injured_0_19 INTEGER, injured_20_64 INTEGER, injured_65_plus INTEGER, injured_total INTEGER,
    total_drivers INTEGER, motorcycles INTEGER, trucks INTEGER, bicycles INTEGER, scooters INTEGER,
    private_cars INTEGER, vehicles_total INTEGER, accident_index DOUBLE, snapshot_yearmonth INTEGER,
    source_file VARCHAR, loaded_at TIMESTAMP);
CREATE TABLE accidents_by_municipality (city_code INTEGER, municipal_code INTEGER, area_sqkm DOUBLE,
    total_accidents INTEGER, killed INTEGER, severely_injured INTEGER, slightly_injured INTEGER,
    pedestrians_injured INTEGER, electric_vehicle_injured INTEGER, injured_0_19 INTEGER,
    injured_20_64 INTEGER, injured_65_plus INTEGER, injured_total INTEGER, total_drivers INTEGER,
    motorcycles INTEGER, trucks INTEGER, bicycles INTEGER, scooters INTEGER, private_cars INTEGER,
    vehicles_total INTEGER, accident_index DOUBLE, snapshot_yearmonth INTEGER,
    source_file VARCHAR, loaded_at TIMESTAMP);
CREATE TABLE dim_settlement (city_code INTEGER, city_name_he VARCHAR, city_name_en VARCHAR,
    region_code INTEGER, region_name VARCHAR, regional_council_name VARCHAR);
CREATE VIEW v_casualty_accidents AS SELECT * FROM accidents WHERE case_type_code = 1;
CREATE VIEW v_casualty_involved  AS SELECT * FROM involved  WHERE case_type_code = 1;
CREATE VIEW v_accidents_weather AS SELECT a.accident_id, a.case_type_code, a."year", a.accident_date, a.hour_of_day,
    a.severity_code, a.severity_label, a.city_name, a.latitude, a.longitude, a.weather_label AS cbs_weather_label,
    a.road_surface_label AS cbs_road_surface_label, w.temperature_c, w.precipitation_mm, w.humidity_pct,
    w.wind_speed_kmh, w.weather_code AS era5_weather_code, d.description_en AS era5_weather_en,
    d.description_he AS era5_weather_he
    FROM accidents AS a
    LEFT JOIN weather_hourly AS w ON (((w.cell_id = a.weather_cell_id) AND (w.observed_at = date_trunc('hour', a.accident_timestamp))))
    LEFT JOIN dim_weather_code AS d ON ((d.weather_code = w.weather_code));
"""


# P13 accident columns as ALTERs, applied only by build_fixture_db: studio_fixture.py shares the base DDL
# and inserts 33-value rows — appending columns to the shared CREATE TABLE would break its positional insert
DDL_P13 = """
ALTER TABLE accidents ADD COLUMN day_of_week SMALLINT;
ALTER TABLE accidents ADD COLUMN day_of_week_label VARCHAR;
ALTER TABLE accidents ADD COLUMN light_code SMALLINT;
ALTER TABLE accidents ADD COLUMN light_label VARCHAR;
ALTER TABLE accidents ADD COLUMN speed_limit_label VARCHAR;
ALTER TABLE accidents ADD COLUMN road_shape_label VARCHAR;
"""


def _ts(year, month, night):
    return dt.datetime(year, month, 15, 22 if night else 10, 30)


def _acc_row(aid, case, year, month, sev, rt, road1=None, road_km=None, nu=0, uj=0, city=None, weather=1,
             dn=1, cell=None, nu_name=None, geo=True, swap=False):
    if city is None:
        city = 5000 if rt in (1, 2) else 0
    night = dn == 5
    # the police record a junction's two streets in either order (live: 5,684 keys carry a swapped pair)
    streets = (None, None) if uj != 777 else (("רחוב ב", "רחוב א") if swap else ("רחוב א", "רחוב ב"))
    # coordinates exist iff the row has a weather cell (the live pattern), deterministic per location: urban rows
    # by junction/city, interurban rows by km/road — so the map's mean points are hand-derivable
    if cell and geo:
        if rt in (1, 2):
            lat, lon = 32.0 + uj / 10000, 34.0 + city / 10000
        else:
            lat, lon = 32.0 + (road_km or 0) / 1000, 35.0 + (road1 or 0) / 100
    else:
        lat = lon = None
    # P13 columns, deterministic (no RNG): the Israeli week keys 1 = ראשון (Sunday) off the real calendar date;
    # the weather-9 row doubles as the unknown-hour/lighting trap (hour_of_day NULL while the timestamp keeps its
    # time — the matrix must read the column, not the timestamp); speed 0 (the live sentinel) and a NULL road
    # shape ride on the off-road row (rt 5); rt 3 carries shape code 9 'אחר' (the 2011 trap)
    date = dt.date(year, month, 15)
    dow = (date.weekday() + 1) % 7 + 1
    hour = None if weather == 9 else (22 if night else 10)
    light = None if weather == 9 else (3 if night else 1)
    speed = 0 if rt == 5 else (1 if rt in (1, 2) else 4)
    shape = None if rt == 5 else (8 if rt in (1, 2) else (9 if rt == 3 else 5))
    return (aid, case, year, month, date, sev, SEV[sev], rt, ROAD[rt],
            road1, road_km, nu, nu_name, uj, city, CITY.get(city), streets[0],
            streets[1], weather, WEATHER[weather], dn, DAYNIGHT[dn], hour,
            _ts(year, month, night), cell, lat, lon, "יבש", shape, None, None, None, speed,   # carriageway/surface codes stay NULL (P4)
            dow, DOW[dow], light, LIGHT.get(light), SPEED[speed], SHAPE.get(shape))


def _inv_row(aid, pid, case, year, month, inj, ctype=2, age=5, age_label="20-24", veh=1, sex=1, vehicle_num=1,
             safety=None, pop=1):
    return (aid, vehicle_num, pid, case, year, month, inj, INJ[inj], ctype, CTYPE.get(ctype), age, age_label,
            veh, VTYPE.get(veh) if veh is not None else None, sex, SEX[sex], safety, pop)


def build_fixture_db(path) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    for stmt in (DDL + DDL_P13).strip().split(";"):
        if stmt.strip():
            con.execute(stmt)
    acc, inv, weather = [], [], []
    # P1 rows
    for aid, year, month, sev, road, people in P1_CASUALTY:
        acc.append(_acc_row(aid, 1, year, month, sev, road))
        for pid, code in enumerate(people, start=1):
            inv.append(_inv_row(aid, pid, 1, year, month, code))
    for aid, year, month, road in P1_DAMAGE:
        acc.append(_acc_row(aid, 3, year, month, 3, road))
    for aid, pid, case, year, month, code in P1_DAMAGE_INVOLVED:
        inv.append(_inv_row(aid, pid, case, year, month, code))
    # P2 rows
    for key, aid, year, month, sev, rt, road1, road_km, nu, uj, city, w, dn, cell, people in P2_CASUALTY:
        acc.append(_acc_row(aid, 1, year, month, sev, rt, road1, road_km, nu, uj, city, w, dn, cell,
                            "צומת העשור" if nu == 433 else None, geo=key not in NO_GEO, swap=key in SWAPPED_STREETS))
        for pid, (inj, ctype, age, age_label, veh, sex) in enumerate(people, start=1):
            inv.append(_inv_row(aid, pid, 1, year, month, inj, ctype, age, age_label, veh, sex))
        if cell:
            precip, temp = WEATHER_SPECIAL.get(key, (0.0, 25.0))
            weather.append((cell, dt.datetime(year, month, 15, 22 if dn == 5 else 10, 0), temp, precip, 50.0, 10.0,
                            61 if precip > 0.1 else 1))
    for y in P2_DAMAGE_YEARS:
        km_null = y in (2017, 2018)
        acc.append(_acc_row(y * 1_000_000 + 1, 3, y, 8, 3, 4, 1, 15.0))
        acc.append(_acc_row(y * 1_000_000 + 2, 3, y, 9, 3, 4, 1, 25.0))
        acc.append(_acc_row(y * 1_000_000 + 3, 3, y, 10, 3, 3, 9, None if km_null else 1000.0, nu=433, nu_name="צומת העשור"))
        acc.append(_acc_row(y * 1_000_000 + 4, 3, y, 11, 3, 3, 9, None if km_null else 1010.0, nu=433, nu_name="צומת העשור"))
    con.executemany("INSERT INTO accidents VALUES (" + ",".join("?" * 39) + ")", acc)
    con.executemany("INSERT INTO involved VALUES (" + ",".join("?" * 18) + ")", inv)
    con.executemany("INSERT INTO vehicles VALUES (?,?,?,?,?)", VEHICLES)
    con.executemany("INSERT INTO fleet_motorcycles VALUES (?,?,?,?,?,?)", FLEET_MOTORCYCLES)
    con.executemany("INSERT INTO traffic_adt_asof VALUES (?,?,?,?,?,?,?,?)", TRAFFIC_ADT_ASOF)
    con.executemany("INSERT INTO traffic_segments VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(r, s, k0, k1, nf, nt, "interurban", "loop", y, dt.datetime(y, 1, 1))
                     for r, s, k0, k1, nf, nt, y in TRAFFIC_SEGMENTS])
    con.executemany("INSERT INTO vehicle_cells VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(y, b, 10000, 1300.0, 0.1 if b == 0 else 0.0, 15000.0, 9000, 3, exp, inv_, ksi, fat)
                     for y, b, exp, inv_, ksi, fat in VEHICLE_CELLS]
                    + [(y, b, fleet, 1300.0, 0.0, 0.0, 0, 0, 0.0, 0, 0, 0) for y, b, fleet in ZERO_EXPOSURE_CELLS])
    con.executemany("INSERT INTO dim_junction_nonurban VALUES (?,?,?,?,?,?,?,?,?)",
                    [(433, 9, 90, 100.0, "צומת העשור", 200000.0, 700000.0, 32.1, 35.1),
                     (433, 90, 9, 5.0, "צומת העשור", 200001.0, 700001.0, 32.1001, 35.1001),   # duplicated code
                     (500, 9, 91, 150.0, "צומת אחר", 200100.0, 700100.0, 32.2, 35.2)])
    # the urban dimension row carries NO coordinates (live: 31 % of dim_junction_urban) → the map falls back to the
    # mean of the junction's own accidents
    con.execute("INSERT INTO dim_junction_urban VALUES (777, 5000, 11, 12, NULL, NULL, NULL, NULL)")
    con.executemany("INSERT INTO weather_hourly VALUES (?,?,?,?,?,?,?)", weather)
    con.executemany("INSERT INTO dim_weather_code VALUES (?,?,?)", [(1, "clear", "בהיר"), (61, "rain", "גשם")])
    # P12: the dictionary the explain faces decode hover values from — one older-year row proves the
    # arg_max(label_he, year) "latest reading wins" rule; involved vehicle types live under vehicle_type_code
    con.executemany("INSERT INTO code_lookups VALUES (?,?,?,?,?)", CODE_LOOKUPS)
    # P14: the geographic snapshot universe (index planted == density; vehicle-mix columns stay 0 — unused)
    con.executemany("INSERT INTO accidents_by_taz VALUES (" + ",".join("?" * 26) + ")",
                    [(taz, city, pop, lu, area, acc, k, sv, sl, ped, ev, a0, a1, a2, inj,
                      0, 0, 0, 0, 0, 0, 0, acc / (area / 1e6), 202604, "fixture_taz.xlsx",
                      dt.datetime(2026, 4, 1))
                     for taz, city, pop, lu, area, acc, k, sv, sl, ped, ev, a0, a1, a2, inj in TAZ_ZONES])
    con.executemany("INSERT INTO accidents_by_municipality VALUES (" + ",".join("?" * 24) + ")",
                    [(city, mc, area, acc, k, sv, sl, ped, 0, 0, 0, 0, inj,
                      0, 0, 0, 0, 0, 0, 0, acc / area, 202604, "fixture_muni.xlsx", dt.datetime(2026, 4, 1))
                     for city, mc, area, acc, k, sv, sl, ped, inj in MUNICIPALITIES])
    con.executemany("INSERT INTO dim_settlement VALUES (?,?,?,?,?,?)", SETTLEMENTS)
    con.close()


@pytest.fixture()
def ctx(tmp_path) -> Context:
    path = tmp_path / "accidents_test.duckdb"
    build_fixture_db(path)
    nl2sql_engine.configure(data_dir=tmp_path)     # never touch the real one (configure() is process-global)
    yield Context(db_path=str(path))
    nl2sql_engine.configure(data_dir=None)


@pytest.fixture()
def studio_ctx(tmp_path) -> Context:
    """The synthetic studio panel DB (60 segments x 2016-2024, deterministic) with its own tmp data dir."""
    from studio_fixture import build_studio_db

    path = tmp_path / "studio_test.duckdb"
    build_studio_db(path)
    nl2sql_engine.configure(data_dir=tmp_path)
    yield Context(db_path=str(path))
    nl2sql_engine.configure(data_dir=None)


@pytest.fixture()
def other_ctx(tmp_path) -> Context:
    import duckdb

    path = tmp_path / "other.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE t (x INTEGER)")
    con.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
    con.close()
    nl2sql_engine.configure(data_dir=tmp_path)
    yield Context(db_path=str(path))
    nl2sql_engine.configure(data_dir=None)
