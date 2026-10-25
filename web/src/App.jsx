import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { dbFromUrl, listConnections, listModules, runAction, setUrlParam, subscribeBusy, tabFromUrl } from "./api.js";
import { TABS, tabOf } from "./tabs.js";
import Header from "./components/Header.jsx";
import TriageBox from "./components/TriageBox.jsx";
import ActionPanel from "./components/ActionPanel.jsx";
import TrendCompare from "./components/TrendCompare.jsx";
import StatCards from "./components/StatCards.jsx";
import StudioIntro from "./components/StudioIntro.jsx";
import Workbench from "./components/Workbench.jsx";
import Empty from "./components/Empty.jsx";

// P10: the map stack (maplibre + deck.gl) rides its own lazy chunk — the other tabs load exactly as before,
// and a map-stack failure is isolated to this tab. The chunk is fetched on the tab's FIRST activation only.
const MapTab = React.lazy(() => import("./components/map/MapTab.jsx"));

export default function App() {
  const urlDb = useMemo(() => dbFromUrl(), []);
  const [db, setDb] = useState(urlDb);
  const [dbSource, setDbSource] = useState(urlDb ? "url" : "");
  const [boot, setBoot] = useState("");
  const [actions, setActions] = useState(null);        // {name: decl}
  const [problems, setProblems] = useState([]);
  const [version, setVersion] = useState("");
  const [about, setAbout] = useState(null);
  const runParam = useMemo(() => new URLSearchParams(window.location.search).get("run") || "", []);
  const [tab, setTab] = useState(() => {
    const wanted = tabFromUrl();
    const known = TABS.some((t) => t.id === wanted) ? wanted : "";
    return known || tabOf(runParam) || TABS[0].id;
  });
  const [focus, setFocus] = useState("");               // action name to scroll to
  const [prefill, setPrefill] = useState({});           // {action: {input: value}}
  const [mapMounted, setMapMounted] = useState(false);  // P10: lazy chunk fetched on first activation, kept mounted after
  const [busyN, setBusyN] = useState(0);                // P13: api.js's ref-counted in-flight run count

  useEffect(() => { if (tab === "map") setMapMounted(true); }, [tab]);
  useEffect(() => subscribeBusy(setBusyN), []);

  // 1. the connection: ?db= from the sidebar link; otherwise a duckdb connection named for accidents, else the most
  //    recently used one (eda precedent) — and the header says it was a guess
  useEffect(() => {
    if (urlDb) return;
    listConnections()
      .then((conns) => {
        const list = Array.isArray(conns) ? conns : conns?.connections || [];
        const byUse = [...list].sort((a, b) => String(b.last_used || "").localeCompare(String(a.last_used || "")));
        const likely = byUse.find((c) => /accident/i.test(String(c.name)));
        const pick = likely || byUse[0];
        if (pick) { setDb(pick.name); setDbSource("fallback"); }
        else setBoot("אין ?db= בכתובת ואין חיבורים — פתחו את העמוד מהסרגל של האפליקציה כדי שיידע את החיבור");
      })
      .catch((e) => setBoot(`אין ?db= בכתובת ולא ניתן לקרוא את רשימת החיבורים: ${e.message}`));
  }, [urlDb]);

  // 2. the declarations drive the forms
  useEffect(() => {
    listModules()
      .then((m) => {
        const mod = (m.modules || []).find((x) => x.name === "roadsafety");
        setProblems((m.problems || []).filter((p) => String(p.name).includes("roadsafety")));
        if (!mod) { setActions({}); return; }
        setActions(Object.fromEntries(mod.actions.map((a) => [a.name, a])));
      })
      .catch((e) => setBoot(`לא ניתן לקרוא את רשימת המודולים: ${e.message}`));
  }, []);

  const [aboutTick, setAboutTick] = useState(0);
  const onDone = useCallback((name) => {
    // a studio action can change the deployed model — refresh the header strip without a reload
    if (name.startsWith("studio_")) setAboutTick((t) => t + 1);
  }, []);

  // 3. the header strip
  useEffect(() => {
    if (!db) return;
    setAbout(null);
    runAction("about", db, {})
      .then((res) => {
        setAbout(res);
        const m = String(res.data || "").match(/nl2sql-roadsafety-lab (\d+\.\d+\.\d+)/);
        if (m) setVersion(m[1]);
      })
      .catch((e) => setAbout({ kind: "error", data: e.message }));
    document.title = `🚦 מעבדת הבטיחות בדרכים · ${db}`;
  }, [db, aboutTick]);

  useEffect(() => { setUrlParam("tab", tab); }, [tab]);

  const goTab = useCallback((id) => { setTab(id); }, []);

  const onRoute = useCallback((action) => {
    const t = tabOf(action);
    if (t) { goTab(t); setFocus(""); setTimeout(() => setFocus(action), 50); }
  }, [goTab]);

  const onHandoff = useCallback((siteKey, extra) => {
    if (!siteKey) return;
    // extra carries e.g. ab_scan's change_year so the discovered candidate lands in before_after pre-set
    setPrefill((p) => ({ ...p, before_after: { site: siteKey, ...(extra || {}) } }));
    onRoute("before_after");
  }, [onRoute]);

  // P10: the map panel's second hand-off — the full TreeSHAP story for the clicked segment
  const onExplain = useCallback((roadSeg) => {
    if (!roadSeg) return;
    setPrefill((p) => ({ ...p, studio_explain: { site: roadSeg } }));
    onRoute("studio_explain");
  }, [onRoute]);

  return (
    <div className="page">
      <Header db={db} about={about} version={version} dbSource={dbSource} busy={busyN > 0} />
      {boot && <div className="error">{boot}</div>}
      {problems.length > 0 && (
        <div className="error">
          המודול accidents מדווח על בעיה: {problems.map((p) => `${p.name}: ${p.reason}`).join(" · ")}
          {" "}— אחרי התקנה צריך להפעיל את האפליקציה מחדש.
        </div>
      )}
      {/* P13: KPI strip parsed from the SAME about card the header uses — no extra fetch */}
      <StatCards about={about} />
      <nav className="tabs" aria-label="tabs">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={t.id === tab ? "on" : ""} onClick={() => goTab(t.id)}>{t.label}</button>
        ))}
      </nav>
      {db && <TriageBox db={db} onRoute={onRoute} />}
      {actions === null && <div className="empty small">טוען את הפעולות…</div>}
      {/* every tab stays mounted (hidden when inactive): answers, edited inputs and the map survive a tab switch */}
      {actions && TABS.map((t) => (
        <div key={t.id} hidden={t.id !== tab} className={`tab-body${t.custom ? " map-full" : ""}`}>
          {t.custom ? (
            (mapMounted || t.id === tab) ? (
              <Suspense fallback={<div className="empty small">טוען את המפה…</div>}>
                <MapTab db={db} active={t.id === tab} onHandoff={onHandoff} onExplain={onExplain} />
              </Suspense>
            ) : null
          ) : (<>
            {t.id === "studio" && <StudioIntro />}
            {/* P13r2: the one-click cockpit ABOVE the full panels — in addition, never instead */}
            {t.id === "studio" && (
              <Workbench db={db} actions={actions} active={t.id === tab}
                         onRoute={onRoute} onHandoff={onHandoff} onExplain={onExplain} />
            )}
            {t.actions.length === 0 && <Empty title={t.label} text={t.empty} />}
            {t.actions.map((name) => {
              const decl = actions[name];
              if (!decl) return <Empty key={name} title={name} text="הפעולה אינה מותקנת בגרסה הזו." />;
              // P11: trend gets the compare-capable panel (up to 3 composed runs); everything else unchanged
              const Panel = name === "trend" ? TrendCompare : ActionPanel;
              return (
                <Panel key={name} decl={decl} db={db} onRoute={onRoute} onHandoff={onHandoff} onExplain={onExplain}
                       prefill={prefill[name]} focus={focus === name} autorun={runParam === name}
                       active={t.id === tab} onDone={onDone} />
              );
            })}
          </>)}
        </div>
      ))}
      <footer className="footer">
        <span>מקור הנתונים: הלשכה המרכזית לסטטיסטיקה (למ״ס); עיבוד: מעבדת הבטיחות בדרכים</span>
        <span className="ltr">Layer 1 · /page/accidents/ · every answer also renders on 🧩 Modules (Layer 0)</span>
      </footer>
    </div>
  );
}
