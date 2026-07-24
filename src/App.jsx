import { useCallback, useMemo, useState } from "react";
import AgentOperations from "./components/AgentOperations";
import AuditReview from "./components/AuditReview";
import DashboardHeader from "./components/DashboardHeader";
import DataQuality from "./components/DataQuality";
import DecisionDrawer from "./components/DecisionDrawer";
import ModelDataset from "./components/ModelDataset";
import Overview from "./components/Overview";
import Sidebar from "./components/Sidebar";
import WorkflowApis from "./components/WorkflowApis";
import { useDashboard } from "./hooks/useDashboard";

const PAGES = {
  overview: { title: "Dashboard", component: Overview },
  operations: { title: "Agent Operations", component: AgentOperations },
  quality: { title: "Data Quality / CACTUV", component: DataQuality },
  model: { title: "Dataset & Model", component: ModelDataset },
  workflow: { title: "Workflow & APIs", component: WorkflowApis },
  audit: { title: "Audit & Manual Review", component: AuditReview },
};

const RANGE_BUTTONS = [
  ["week", "This Week"],
  ["today", "Today"],
  ["month", "This Month"],
  ["year", "This Year"],
];

export default function App() {
  const initial = window.location.hash.replace("#", "");
  const [activePage, setActivePage] = useState(PAGES[initial] ? initial : "overview");
  const [range, setRange] = useState("week");
  const [selectedDecision, setSelectedDecision] = useState(null);
  const { data, loading, error, partialErrors, refresh } = useDashboard({ range });
  const page = PAGES[activePage] || PAGES.overview;
  const PageComponent = page.component;

  const user = useMemo(() => {
    try { return JSON.parse(sessionStorage.getItem("user") || "{}"); } catch { return {}; }
  }, []);

  const changePage = useCallback((id) => setActivePage(id), []);

  return (
    <div className="application-shell">
      <Sidebar
        activePage={activePage}
        onChange={changePage}
        email={user.email || "SNOC Administrator"}
        role={user.role || "ADMIN"}
      />

      <main className="dashboard-main">
        <DashboardHeader
          title={page.title}
          mode={data.mode}
          generatedAt={data.generatedAt}
          loading={loading}
          onRefresh={refresh}
        />

        <section className="date-filter-bar" aria-label="Dashboard time range">
          <span className="date-trigger">Date ▾</span>
          {RANGE_BUTTONS.map(([id, label]) => (
            <button type="button" key={id} className={range === id ? "active" : ""} onClick={() => setRange(id)}>
              {label}
            </button>
          ))}
        </section>

        {error ? <div className="dashboard-notice warning"><strong>Demo mode.</strong> {error}</div> : null}
        {partialErrors.length > 0 && partialErrors.length < 9 ? (
          <div className="dashboard-notice neutral">Some optional API sections are unavailable. Available live data is combined with clearly marked deterministic fixtures.</div>
        ) : null}
        {loading ? <div className="dashboard-loading"><span /></div> : null}

        <div className="dashboard-page-content">
          <PageComponent data={data} onSelect={setSelectedDecision} />
        </div>

        <footer className="dashboard-footer">
          <span>SNOC AI & Data Quality Command Center</span>
          <span>UC5 • Read-only analytics • ESI Logis visual identity</span>
        </footer>
      </main>

      <DecisionDrawer item={selectedDecision} onClose={() => setSelectedDecision(null)} />
    </div>
  );
}
