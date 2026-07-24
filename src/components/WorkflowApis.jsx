import { CheckCircle2, CircleAlert, Mail, Network, ShieldCheck, Sparkles } from "lucide-react";
import { MetricRibbon, StatusBadge } from "./Primitives";

const ICONS = [Mail, ShieldCheck, Sparkles, Network, Mail, CheckCircle2];

export default function WorkflowApis({ data }) {
  return (
    <>
      <MetricRibbon items={[
        { label: "Workflow stages", value: data.workflow.length },
        { label: "Healthy stages", value: data.workflow.filter((item)=>item.status === "Healthy").length },
        { label: "Degraded stages", value: data.workflow.filter((item)=>item.status === "Degraded").length },
        { label: "Safety mode", value: "Enabled" },
      ]} />
      <section className="workflow-grid">
        {data.workflow.map((step,index)=>{const Icon=ICONS[index]||CircleAlert; return <article className="workflow-card dashboard-card" key={step.id}><div className="workflow-number">0{index+1}</div><Icon size={27}/><h2>{step.title}</h2><StatusBadge value={step.status}/><dl><div><dt>Processed</dt><dd>{step.processed}</dd></div><div><dt>Errors</dt><dd>{step.errors}</dd></div><div><dt>Average</dt><dd>{step.averageMs} ms</dd></div><div><dt>Last success</dt><dd>{step.lastSuccess}</dd></div></dl></article>})}
      </section>
      <section className="api-catalog dashboard-card"><div className="table-title-row"><div><h2>SNOC API catalog</h2><p>Read-only operational health; no execution buttons</p></div></div><div className="api-grid">{["POST /create-account","POST /reset-password/{pos_code}","POST /unlock-account/{pos_code}","POST /update-otp/{pos_code}/{new_otp}"].map((endpoint)=><div key={endpoint}><code>{endpoint}</code><StatusBadge value="Healthy" /></div>)}</div></section>
    </>
  );
}
