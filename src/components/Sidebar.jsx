"use client";

import { AnimatePresence, motion, useAnimationControls } from "framer-motion";
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
  Workflow,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

// Same nav shape as ESI Logis' Side.jsx (icon / text / href / submenu),
// wired to this dashboard's pages instead of the maintenance-app pages.
const NAV_ITEMS = [
  { id: "overview", icon: ChartNoAxesCombined, text: "Dashboard", submenu: [] },
  { id: "operations", icon: Bell, text: "Agent Operations", submenu: [] },
  { id: "quality", icon: DatabaseZap, text: "Data Quality", submenu: [] },
  { id: "model", icon: Bot, text: "Dataset & Model", submenu: [] },
  { id: "workflow", icon: Workflow, text: "Workflow & APIs", submenu: [] },
  { id: "audit", icon: FileClock, text: "Audit & Review", submenu: [] },
];

export default function Sidebar({ activePage, onChange, email = "SNOC Administrator", role = "ADMIN" }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSidebarFullyOpen, setIsSidebarFullyOpen] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const controls = useAnimationControls();
  const itemRefs = useRef([]);

  useEffect(() => {
    if (isOpen) {
      controls.start({ width: 250 }).then(() => setIsSidebarFullyOpen(true));
    } else {
      setIsSidebarFullyOpen(false);
      controls.start({ width: 130 });
    }
  }, [isOpen, controls]);

  useEffect(() => {
    const onHash = () => {
      const hash = window.location.hash.replace("#", "");
      if (NAV_ITEMS.some((item) => item.id === hash)) onChange(hash);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [onChange]);

  function navigate(id) {
    window.location.hash = id;
    onChange(id);
    setMobileOpen(false);
  }

  function handleLogout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("user");
    window.location.assign("/");
  }

  const expanded = isOpen || mobileOpen;

  return (
    <>
      <button
        type="button"
        className="fixed left-3 top-3 z-[95] grid h-10 w-10 place-items-center rounded-[10px] bg-black text-white md:hidden"
        onClick={() => setMobileOpen((value) => !value)}
        aria-label="Toggle navigation"
      >
        {mobileOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
      </button>

      <motion.nav
        className={`fixed left-1 top-1 z-50 flex flex-col rounded-2xl bg-black transition-transform duration-300 ${
          mobileOpen ? "translate-x-0" : "-translate-x-[120%]"
        } md:translate-x-0`}
        style={{ height: "calc(100vh - 8px)" }}
        role="navigation"
        initial={{ width: 130 }}
        animate={mobileOpen ? { width: 250 } : controls}
        transition={{ duration: 0.3 }}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
      >
        {/* Logo */}
        <div className="flex w-full items-center justify-center p-5 pt-10">
          <div className="flex flex-col items-center leading-[0.8] font-oxanium font-extrabold tracking-tighter text-white">
            <span className="text-[28px]" style={{ textShadow: "3px 3px 0 #0060b4" }}>5</span>
            <span className="text-[15px]" style={{ textShadow: "3px 3px 0 #0060b4" }}>PRAKTORES</span>
          </div>
        </div>

        {/* Divider */}
        <div className="flex w-full flex-col items-center justify-center">
          <motion.div
            className="h-[2px] bg-white"
            initial={{ width: "60%" }}
            animate={{ width: expanded ? "80%" : "60%" }}
            transition={{ duration: 0.3 }}
          />
        </div>

        {/* Navigation items */}
        <ul className="flex h-8/12 w-full flex-col">
          {NAV_ITEMS.map((item, index) => {
            const Icon = item.icon;
            const active = activePage === item.id;
            const hovered = hoveredIndex === index;
            return (
              <li
                key={item.id}
                ref={(el) => (itemRefs.current[index] = el)}
                className="relative w-full p-4 pl-4 sm:p-6 sm:pl-6 md:p-9 md:pl-8"
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                <button
                  type="button"
                  onClick={() => navigate(item.id)}
                  aria-current={active ? "page" : undefined}
                  title={!expanded ? item.text : undefined}
                  className="flex w-full items-center gap-2 sm:gap-3 md:gap-4"
                >
                  <div className="relative ml-2 h-[20px] w-[20px] sm:ml-3 sm:h-[22px] sm:w-[22px] md:ml-4 md:h-[25px] md:w-[25px]">
                    <Icon
                      size={25}
                      strokeWidth={1.85}
                      className="h-full w-full"
                      color={hovered || active ? "#EA8B00" : "#FFFFFF"}
                    />
                  </div>
                  {expanded && (
                    <motion.span
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.1 }}
                      className={`whitespace-nowrap font-oxanium text-xs font-semibold sm:text-sm md:text-base ${
                        hovered || active ? "text-[#EA8B00]" : "text-white"
                      }`}
                    >
                      {item.text}
                    </motion.span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        {/* Bottom profile info */}
        <div className="mt-auto flex w-full flex-col items-start justify-center p-3 sm:p-4 md:p-6">
          <div className="flex h-12 w-full flex-row items-center">
            <CircleUserRound
              size={40}
              strokeWidth={1.5}
              className="ml-2 h-8 w-8 text-white sm:ml-2.5 sm:h-10 sm:w-10 md:ml-[13px] md:h-12 md:w-12"
            />
            <div className="flex h-full w-full flex-col justify-start">
              {expanded && (
                <>
                  <h1 className="ml-0.5 truncate whitespace-nowrap font-outfit text-[10px] text-white sm:text-[12px] md:text-[13px]">
                    {email}
                    <br />
                    <span className="text-[8px] font-extralight opacity-55 sm:text-[10px] md:text-[13px]">{role}</span>
                  </h1>
                  <AnimatePresence>
                    {isSidebarFullyOpen && (
                      <motion.button
                        onClick={handleLogout}
                        className="mt-1 flex items-center justify-center gap-1 rounded-4xl border-2 border-white bg-black py-0.5 text-xs text-white transition-colors hover:bg-white hover:text-black"
                        initial={{ opacity: 0, y: 10, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 5, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 300, damping: 20, delay: 0.1 }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        <LogOut size={12} /> Log out
                      </motion.button>
                    )}
                  </AnimatePresence>
                </>
              )}
            </div>
          </div>
        </div>
      </motion.nav>

      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 border-0 bg-black/35 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
}
