import { X } from "lucide-react";
export default function DecisionDrawer({ item, onClose }) {
  if (!item) return null;
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="decision-drawer" onMouseDown={(event)=>event.stopPropagation()}><button type="button" className="drawer-close" onClick={onClose}><X size={20}/></button><p>Agent decision</p><h2>{item.id}</h2><dl>{Object.entries(item).map(([key,value])=><div key={key}><dt>{key.replace(/([A-Z])/g," $1")}</dt><dd>{String(value ?? "—")}</dd></div>)}</dl></aside></div>;
}
