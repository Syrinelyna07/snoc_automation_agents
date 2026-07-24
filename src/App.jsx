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

        <section
          className="mb-2 flex w-full flex-wrap items-center gap-2 border px-4 py-2 sm:px-14 sm:py-4"
          aria-label="Dashboard time range"
        >
          <button
            type="button"
            className="rounded-md border-none bg-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 sm:px-4 sm:py-2 sm:text-sm"
          >
            Date ▾
          </button>
          <div className="flex flex-wrap gap-2">
            {RANGE_BUTTONS.map(([id, label]) => (
              <button
                type="button"
                key={id}
                onClick={() => setRange(id)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium sm:px-4 sm:py-2 sm:text-sm ${
                  range === id ? "bg-black text-white" : "bg-gray-50 text-gray-800"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
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
