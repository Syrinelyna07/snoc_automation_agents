# SNOC AI Agent — Dashboard (React + Vite)

This is the React conversion of the SNOC AI Agent operational dashboard.
The visual design, layout, spacing, and CSS are unchanged from the original
HTML/CSS/JS version — only the implementation is now componentized React.

## Structure

```
react-project/
├── index.html                  Vite entry HTML
├── package.json
├── vite.config.js
└── src/
    ├── main.jsx                 React root
    ├── App.jsx                  Wires all sections together
    ├── index.css                Original stylesheet (unchanged)
    ├── data/
    │   └── mockData.js          Mock data generation (senders, requests, alerts)
    ├── hooks/
    │   └── useDashboard.js       Central state + live simulation (every 4s)
    └── components/
        ├── ChartCanvas.jsx       Reusable Chart.js wrapper
        ├── Sidebar.jsx
        ├── TopNav.jsx
        ├── CriticalOperations.jsx   (Active Alerts)
        ├── PlatformHealth.jsx       (KPI row)
        ├── LiveOperations.jsx       (Timeline + Execution Console)
        ├── AIIntelligence.jsx       (Intent/Confidence charts, entities, model info)
        ├── TimeIntelligence.jsx     (Hourly/Weekly charts, heatmap)
        ├── BusinessIntel.jsx        (Funnel, regional chart, blocking analysis)
        ├── BusinessImpact.jsx       (ROI metrics, API health)
        ├── OperationalQuality.jsx   (Quality metric cards)
        ├── AuditTrail.jsx           (Filterable/searchable table)
        └── DecisionDrawer.jsx       (AI Decision Inspector drawer)
```

## Running locally

```bash
cd react-project
npm install
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

## Building for production

```bash
npm run build
npm run preview   # to test the production build locally
```

## Notes

- The dashboard's live feed (new requests, alerts, console lines) is simulated
  client-side via `useDashboard.js`, ticking every 4 seconds — same behavior
  as the original vanilla JS version.
- All state lives in React (`useState`/`useEffect`), no external state library.
- Chart.js is used directly (not `react-chartjs-2`) via the `ChartCanvas`
  wrapper component, so charts update in place without re-mounting.
- Click any row in the Timeline or Audit Trail to open the AI Decision
  Inspector drawer.
