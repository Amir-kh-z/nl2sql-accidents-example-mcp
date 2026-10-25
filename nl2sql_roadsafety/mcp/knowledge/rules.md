# הכללים הזהובים · Road Safety Lab (Israel road-accidents database, CBS)

Knowledge for a co-pilot answering over the Road Safety Lab tools. Knowledge only — the numbers below are the
published verification answers, not data.

## Two series in one table — the trap
- `accidents` holds TWO series side by side: `case_type_code = 1` = casualty accidents (people hurt) and
  `case_type_code = 3` = damage-only accidents. Every count of accidents or people uses the casualty series
  unless the question is explicitly about damage-only events.
- Verification (2024): 439 people killed · 5,458 slight-injury accidents · 8,315 casualty accidents. The naive
  "slight accidents" count without the series filter gives ~50,145 — the damage-only series inflates it ~9×.
  `roadsafety_orient(section=trap)` shows both statements.
- Person tables (`involved`, `vehicles`) join accidents on the COMPOSITE key (accident_id, case_type_code) —
  accident ids collide across the two series.
- killed ≠ fatal accidents: people vs events. Say which one you report.

## Coverage
- Data 2005-01-01 … 2024-12-31. Anything after 2024 cannot be answered.
- Years whose person-level records are missing show as gaps (live: 2009), never as zero. A period with no
  rows is a refusal card, never a blank chart.
- Coordinates exist from 2008; the as-of traffic exposure layer covers 2017–2024 only.

## Denominators — counts are not risk
- Every answer names its denominator kind: exposure (vehicle-km, fleet, residents), counts only, none (a rate
  the data cannot support) or not applicable. Counts alone are never "risk": busy roads are also just busy.
- Per-km / per-vkm rates exist for interurban traffic-count SEGMENTS only. Junctions and city streets carry no
  exposure denominator — the tools refuse per-km claims there and say why.
- The site model (`roadsafety_sites rank_by=excess`) screens by excess = observed − expected; junctions never
  get model measures. The severity model is RELATIVE (to the holdout baseline), never an absolute probability.

## Two universes, never compared
- The yearly series (accidents/involved, 2005–2024) and the CUMULATIVE undated publication snapshot
  (accidents_by_taz, accidents_by_municipality) are different universes. Zone and city rankings come from the
  snapshot; never compare their totals with the yearly series.

## What the data cannot say
- Make/model safety: the files carry no plate, VIN or model code — vehicle CELLS (manufacture year × engine
  band) are the finest honest unit. Residence is not location. Weather labels are the officer's, cross-checked
  against measured rain — neither is ground truth.
- Before/after effects are associations (double difference-in-differences against the national network),
  never proof; a discovered change point is a rank score and must be confirmed with mode=evaluate.

## Governance
- Training or deploying a model changes shared state: ask the person, then call `roadsafety_studio` with
  `confirm=true`. Only VALIDATED models deploy; rejected models refuse with the gate's reasons.
- Every answered run lands in the findings ledger (`roadsafety_finding`), refusals included.

## License and credit
- Source: the Central Bureau of Statistics (הלשכה המרכזית לסטטיסטיקה, למ״ס). Every rendered answer carries the
  credit line `מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים` — keep it in
  anything you produce from these answers. The database itself is never copied, shared or uploaded.
