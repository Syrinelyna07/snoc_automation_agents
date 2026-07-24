import { RefreshCcw } from "lucide-react";

export default function DashboardHeader({ title, mode, generatedAt, loading, onRefresh }) {
  const updated = generatedAt
    ? new Date(generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "—";

  return (
    <header className="flex h-[86px] items-center justify-between border-2 border-l-0 border-[#e2e2e2] bg-[#f4f4f5] px-4 sm:px-8 md:px-14">
      <div>
        <h1 className="m-0 font-oxanium text-lg font-semibold sm:text-xl md:text-2xl">{title}</h1>
        <p className="mt-1 hidden text-xs text-[#777] sm:block">SNOC AI &amp; Data Quality Command Center</p>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <span
          className={`hidden rounded-full px-3 py-1.5 text-[11px] font-semibold sm:inline-block ${
            mode === "live" ? "bg-[#eaf8f0] text-[#249c62]" : "bg-[#fff4e4] text-[#a45e00]"
          }`}
        >
          {mode === "live" ? "Live data" : "Demo data"}
        </span>
        <span className="hidden text-[11px] text-[#7b7b7b] md:inline-block">Updated {updated}</span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md bg-white px-3 py-2 text-xs font-medium text-gray-800 shadow-md hover:bg-black hover:text-white disabled:cursor-progress disabled:opacity-60 sm:px-4 sm:text-sm"
        >
          <RefreshCcw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>
    </header>
  );
}
