import { AnimatePresence, motion } from "framer-motion";
import {
  Bell,
  Bot,
  ChartNoAxesCombined,
  CircleUserRound,
  DatabaseZap,
  FileClock,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Workflow,
} from "lucide-react";
import { useEffect, useState } from "react";

const ITEMS = [
  { id: "overview", label: "Overview", icon: ChartNoAxesCombined },
  { id: "operations", label: "Agent Operations", icon: Bell },
  { id: "quality", label: "Data Quality", icon: DatabaseZap },
  { id: "model", label: "Dataset & Model", icon: Bot },
  { id: "workflow", label: "Workflow & APIs", icon: Workflow },
  { id: "audit", label: "Audit & Review", icon: FileClock },
];

export default function Sidebar({ activePage, onChange, email = "SNOC Administrator", role = "ADMIN" }) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const expanded = hovered || pinned || mobileOpen;

  useEffect(() => {
    const onHash = () => {
      const hash = window.location.hash.replace("#", "");
      if (ITEMS.some((item) => item.id === hash)) onChange(hash);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [onChange]);

  function navigate(id) {
    window.location.hash = id;
    onChange(id);
    setMobileOpen(false);
  }

  function logout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("user");
    window.location.assign("/");
  }

  return (
    <>
      <button
        type="button"
        className="mobile-menu-button"
        onClick={() => setMobileOpen((value) => !value)}
        aria-label="Toggle navigation"
      >
        {mobileOpen ? <PanelLeftClose size={21} /> : <PanelLeftOpen size={21} />}
      </button>

      <motion.aside
        className={`esi-sidebar ${expanded ? "expanded" : ""}`}
        animate={{ width: expanded ? 252 : 140 }}
        transition={{ duration: 0.28, ease: "easeOut" }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-label="SNOC dashboard navigation"
      >
        <div className="esi-brand">
          <div className="esi-logo" aria-label="ESI Logis">
            <span className="esi-word">ESI</span>
            <span className="logis-word">LOGIS</span>
            <i />
          </div>
          <AnimatePresence>
            {expanded ? (
              <motion.div className="esi-brand-copy" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <strong>SNOC UC5</strong>
                <span>AI Command Center</span>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <div className="sidebar-divider" />

        <nav className="esi-navigation">
          {ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activePage === item.id;
            return (
              <button
                type="button"
                key={item.id}
                className={`esi-nav-item ${active ? "active" : ""}`}
                onClick={() => navigate(item.id)}
                aria-current={active ? "page" : undefined}
                title={!expanded ? item.label : undefined}
              >
                <Icon size={25} strokeWidth={1.85} />
                <AnimatePresence>
                  {expanded ? (
                    <motion.span initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}>
                      {item.label}
                    </motion.span>
                  ) : null}
                </AnimatePresence>
              </button>
            );
          })}
        </nav>

        <button type="button" className="sidebar-pin" onClick={() => setPinned((value) => !value)} aria-label={pinned ? "Unpin sidebar" : "Pin sidebar"}>
          {pinned ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>

        <div className="esi-profile">
          <CircleUserRound size={47} strokeWidth={1.75} />
          <AnimatePresence>
            {expanded ? (
              <motion.div className="esi-profile-copy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <strong>{email}</strong>
                <span>{role}</span>
              </motion.div>
            ) : null}
          </AnimatePresence>
          {expanded ? (
            <button type="button" className="esi-logout" onClick={logout} aria-label="Log out">
              <LogOut size={18} />
            </button>
          ) : null}
        </div>

        <div className="sidebar-bottom-label">
          <Settings size={14} />
          {expanded ? <span>Safety mode enabled</span> : null}
        </div>
      </motion.aside>
      {mobileOpen ? <button className="mobile-backdrop" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> : null}
    </>
  );
}
