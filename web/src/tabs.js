// PLAN_1 §6: the six tabs — all live since P4 (refusal cards are the empty states: an empty registry or ledger
// answers with what to do next). P10 adds the CUSTOM map tab: its actions list serves triage routing (tabOf),
// but App.jsx renders MapTab (lazy chunk) instead of ActionPanels.
export const TABS = [
  // P13: heat_matrix ships server-side in the same phase — if its wheel isn't installed yet the tab
  // shows the standard "not installed in this version" empty card for it (harmless, self-explaining).
  // severity_profile rides here TOO (also on חומרה): with by=שנה + תצוגה=ספירות it is the three-line
  // severity trend the instructor picked from the rival's Trends tab (P13r2)
  { id: "trends", label: "מגמות", actions: ["trend", "severity_profile", "heat_matrix", "naive_vs_correct"] },
  { id: "hotspots", label: "נקודות תורפה", actions: ["segment_rates", "site_ranking", "hotspot_map"] },
  // Wave 2: the zone actions ship concurrently server-side (same pattern as heat_matrix above) —
  // until the wheel lands, each shows the standard "not installed in this version" empty card.
  { id: "zones", label: "אזורים", actions: ["zone_ranking", "city_ranking"] },
  { id: "map", label: "מפה חיה", actions: ["map_scene", "site_profile"], custom: true },
  { id: "severity", label: "חומרה", actions: ["severity_profile", "severity_predict", "what_if", "severity_explain", "vehicle_cells_ranking", "two_wheelers", "weather_check"] },
  // Wave 2: ab_scan (the network-wide change scan) leads INTO before_after — the scan surfaces
  // candidates, the paired action gives them the confidence interval; reading order = screen order.
  { id: "before_after", label: "לפני/אחרי", actions: ["ab_scan", "before_after"] },
  { id: "studio", label: "סטודיו", actions: ["studio_models", "studio_train_site", "studio_validate", "studio_deploy", "studio_explain", "studio_train_severity", "studio_validate_severity"] },
  { id: "findings", label: "ממצאים", actions: ["ledger_list", "finding_card"] },
];

export function tabOf(action) {
  return TABS.find((t) => t.actions.includes(action))?.id || "";
}
