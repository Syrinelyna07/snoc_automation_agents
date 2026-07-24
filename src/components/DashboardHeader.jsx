import { RefreshCcw } from "lucide-react";

export default function DashboardHeader({ title, mode, generatedAt, loading, onRefresh }) {
  const updated = generatedAt ? new Date(generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";
  return (
    <header className="dashboard-header">
      <div>
        <h1>{title}</h1>
        <p>SNOC AI & Data Quality Command Center</p>
      </div>
      <div className="header-actions">
        <span className={`mode-badge ${mode === "live" ? "live" : "demo"}`}>{mode === "live" ? "Live data" : "Demo data"}</span>
        <span className="last-update">Updated {updated}</span>
        <button type="button" onClick={onRefresh} disabled={loading}>
          <RefreshCcw size={17} className={loading ? "spinning" : ""} />
          Refresh
        </button>
      </div>
      <div className="esi-corner-stripes" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </header>
  );
}
