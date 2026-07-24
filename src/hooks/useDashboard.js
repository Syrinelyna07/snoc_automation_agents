import { useCallback, useEffect, useMemo, useState } from "react";
import { DEMO_DASHBOARD } from "../data/mockData";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function getJson(path, signal) {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function camel(obj) {
  if (Array.isArray(obj)) return obj.map(camel);
  if (!obj || typeof obj !== "object") return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()),
      camel(value),
    ]),
  );
}

function mergeLive(demo, values) {
  const [summary, trends, intents, recent, dqExecutive, dqDimensions, dqRules, model, workflow] = values;
  const liveSummary = summary ? camel(summary) : null;
  const operational = liveSummary?.operational || liveSummary?.summary?.operational;
  const quality = liveSummary?.dataQuality || liveSummary?.summary?.dataQuality || (dqExecutive ? camel(dqExecutive) : null);

  return {
    ...demo,
    mode: values.some(Boolean) ? "live" : "demo",
    generatedAt: liveSummary?.generatedAt || new Date().toISOString(),
    summary: {
      operational: { ...demo.summary.operational, ...(operational || {}) },
      dataQuality: { ...demo.summary.dataQuality, ...(quality || {}) },
    },
    trends: Array.isArray(trends?.items) ? camel(trends.items) : Array.isArray(trends) ? camel(trends) : demo.trends,
    intents: Array.isArray(intents?.items) ? camel(intents.items) : Array.isArray(intents) ? camel(intents) : demo.intents,
    recent: Array.isArray(recent?.items) ? camel(recent.items) : Array.isArray(recent) ? camel(recent) : demo.recent,
    dq: {
      dimensions: Array.isArray(dqDimensions?.items) ? camel(dqDimensions.items) : Array.isArray(dqDimensions) ? camel(dqDimensions) : demo.dq.dimensions,
      rules: Array.isArray(dqRules?.items) ? camel(dqRules.items) : Array.isArray(dqRules) ? camel(dqRules) : demo.dq.rules,
    },
    model: model ? { ...demo.model, ...camel(model) } : demo.model,
    workflow: Array.isArray(workflow?.items) ? camel(workflow.items) : Array.isArray(workflow) ? camel(workflow) : demo.workflow,
  };
}

export function useDashboard({ range = "week" } = {}) {
  const [data, setData] = useState(DEMO_DASHBOARD);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partialErrors, setPartialErrors] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setRefreshKey((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let mounted = true;

    async function load() {
      setLoading(true);
      setError("");
      const routes = [
        `/api/snoc/dashboard/summary?range=${range}`,
        `/api/snoc/dashboard/trends?range=${range}`,
        `/api/snoc/dashboard/intents?range=${range}`,
        `/api/snoc/dashboard/recent?range=${range}`,
        "/api/snoc/dq/executive",
        "/api/snoc/dq/dimensions",
        "/api/snoc/dq/rules",
        "/api/snoc/model/snapshot",
        "/api/snoc/workflow/health",
      ];
      const settled = await Promise.allSettled(routes.map((route) => getJson(route, controller.signal)));
      if (!mounted) return;
      const values = settled.map((result) => (result.status === "fulfilled" ? result.value : null));
      const failures = settled
        .map((result, index) => (result.status === "rejected" ? routes[index] : null))
        .filter(Boolean);
      setPartialErrors(failures);
      setData(mergeLive(DEMO_DASHBOARD, values));
      if (failures.length === routes.length) {
        setError("Backend endpoints are unavailable. Deterministic demo data is displayed.");
      }
      setLoading(false);
    }

    load().catch((reason) => {
      if (!mounted || reason?.name === "AbortError") return;
      setError("Backend unavailable. Deterministic demo data is displayed.");
      setData(DEMO_DASHBOARD);
      setLoading(false);
    });

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [range, refreshKey]);

  return useMemo(
    () => ({ data, loading, error, partialErrors, refresh }),
    [data, loading, error, partialErrors, refresh],
  );
}
