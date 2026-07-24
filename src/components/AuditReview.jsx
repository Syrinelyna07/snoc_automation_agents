import { StatusBadge } from "./Primitives";

export default function AuditReview({ data, onSelect }) {
  function exportCsv() {
    const columns = ["timestamp","id","sender","intent","confidence","posCode","action","status","durationMs","validationError"];
    const csv = [columns.join(","), ...data.recent.map((row)=>columns.map((key)=>JSON.stringify(row[key] ?? "")).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const anchor = document.createElement("a"); anchor.href=url; anchor.download="snoc-audit.csv"; anchor.click(); URL.revokeObjectURL(url);
  }
  return <section className="requests-card dashboard-card"><div className="table-title-row"><div><h2>Audit and manual review</h2><p>Filtered non-sensitive request decisions</p></div><button className="primary-button" type="button" onClick={exportCsv}>Export CSV</button></div><div className="table-scroll"><table><thead><tr><th>Time</th><th>Request</th><th>Sender</th><th>Intent</th><th>Confidence</th><th>POS code</th><th>Validation</th><th>Action</th><th>Status</th><th>Duration</th></tr></thead><tbody>{data.recent.map((row)=><tr key={row.id} onClick={()=>onSelect?.(row)}><td>{row.timestamp}</td><td className="mono-cell">{row.id}</td><td>{row.sender}</td><td>{row.intent}</td><td>{Math.round(row.confidence*100)}%</td><td>{row.posCode}</td><td>{row.validationError}</td><td>{row.action}</td><td><StatusBadge value={row.status}/></td><td>{(row.durationMs/1000).toFixed(2)}s</td></tr>)}</tbody></table></div></section>;
}
