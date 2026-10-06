import { useEffect, useState, type ReactNode } from "react";

import { authMe } from "../../lib/api";
import { operatorInput } from "../../lib/api";
import type { Principal } from "../../lib/types";
import { useTelemetry } from "../../store/useTelemetry";

export type AppPage = "preflight" | "dashboard" | "tasks" | "live" | "safety" | "incidents" | "training" | "fleet" | "assistant";

const NAV = [
  { label: "Pre-Start Safety", helper: "Pre-shift safety precaution checklist", page: "preflight" as AppPage, phase: "00" },
  { label: "Home", helper: "Your shift at a glance", page: "dashboard" as AppPage, phase: "01" },
  { label: "Today’s Work", helper: "Tasks and time left", page: "tasks" as AppPage, phase: "02" },
  { label: "Live Machine", helper: "See it working now", page: "live" as AppPage, phase: "03" },
  { label: "Safety Help", helper: "What to do safely", page: "safety" as AppPage, phase: "04" },
  { label: "What Happened", helper: "Incidents and replay", page: "incidents" as AppPage, phase: "05" },
  { label: "Practice", helper: "Learn by doing", page: "training" as AppPage, phase: "06" },
  { label: "Fleet View", helper: "See every machine", page: "fleet" as AppPage, phase: "07" },
  { label: "Ask CommandGuard", helper: "Ask about the machine", page: "assistant" as AppPage, phase: "08" },
];

export function AppShell({ children, activePage, onNavigate, safetyCleared }: { children: ReactNode; activePage: AppPage; onNavigate: (page: AppPage) => void; safetyCleared: boolean }) {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const { machineId, seatbeltStatus, incident, taskNotice, setSeatbeltStatus, clearTaskNotice } = useTelemetry();
  useEffect(() => { authMe().then((result) => setPrincipal(result.principal)).catch(() => undefined); }, []);
  const toggleSeatbelt = () => {
    setSeatbeltStatus(seatbeltStatus === "Fastened" ? "Unfastened" : "Fastened");
    operatorInput(machineId, "TOGGLE_SEATBELT").catch(() => undefined);
  };
  return (
    <div className="min-h-screen">
      <div className="hud-overlay" />
      <aside className="fixed left-0 top-0 z-30 flex h-full w-16 flex-col gap-1 border-r border-yellow-400/15 bg-black/75 px-1 py-4 backdrop-blur-xl sm:w-52 sm:px-2">
        <div className="mb-4 px-1 sm:px-2">
           <div className="font-mono text-lg font-bold tracking-[0.25em] text-signal">CG</div>
           <div className="mt-1 hidden text-xs font-semibold tracking-[0.18em] text-slate-300 sm:block">COMMANDGUARD</div>
           <div className="hud-label mt-1 hidden sm:block">SMART OPERATOR ASSISTANT</div>
          <div className="boot-line mt-2" />
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => {
            const isAccessible = safetyCleared || item.page === "preflight";
            const isActive = activePage === item.page;
            return (
              <button
                key={item.label}
                title={item.helper}
                aria-label={`${item.label}: ${item.helper}`}
                onClick={() => onNavigate(item.page)}
                disabled={!isAccessible}
                className={
                  "group flex items-center gap-2 rounded px-2 py-2 text-left text-xs transition " +
                  (isActive
                    ? "border border-holo/30 bg-holo/10 text-holo"
                    : isAccessible
                    ? "text-slate-400 hover:border hover:border-carbon-600 hover:bg-carbon-800/60 hover:text-slate-200"
                    : "cursor-not-allowed text-slate-700")
                }
              >
                <span
                  className={
                    "h-1.5 w-1.5 rounded-full " +
                    (isActive ? "bg-holo shadow-glow" : isAccessible ? "bg-carbon-600" : "bg-carbon-800")
                  }
                />
                <span className="hidden tracking-wider sm:inline">{item.label}</span>
                <span className="ml-auto hidden rounded bg-carbon-800 px-1 num text-[9px] text-slate-500 sm:block">{item.phase}</span>
              </button>
            );
          })}
        </nav>
        <div className="hud-label hidden px-2 text-[9px] leading-relaxed text-slate-600 sm:block">
          SYNTHETIC OPERATOR SUPPORT · NOT REAL HARDWARE
        </div>
        {principal && <div className="mt-3 rounded border border-yellow-400/15 bg-carbon-950/40 px-1 py-2 text-center sm:px-2 sm:text-left"><div className="hud-label hidden sm:block">SESSION</div><div className="num text-[9px] text-slate-300 sm:mt-1 sm:text-[10px]">{principal.operator_id}</div><div className="num hidden text-[9px] uppercase text-holo sm:block">{principal.role}</div></div>}
      </aside>
      <main className="pl-16 sm:pl-52">{children}</main>
      {safetyCleared && seatbeltStatus === "Unfastened" && <div role="alert" className="fixed bottom-5 right-5 z-50 w-[min(360px,calc(100vw-2rem))] rounded-xl border border-danger/70 bg-black/90 p-4 shadow-[0_0_35px_rgba(239,68,68,0.28)] backdrop-blur-xl"><div className="flex items-start gap-3"><div className="mt-1 h-3 w-3 rounded-full bg-danger shadow-[0_0_14px_rgba(239,68,68,0.9)]" /><div className="min-w-0 flex-1"><div className="num text-xs font-bold tracking-widest text-danger">SEATBELT NOT FASTENED</div><p className="mt-2 text-sm leading-relaxed text-slate-200">The machine is not in a safe operating state. Fasten your seatbelt before moving.</p><button onClick={toggleSeatbelt} className="mt-3 rounded border border-good/60 bg-good/10 px-3 py-2 num text-[10px] font-semibold tracking-widest text-good">FASTEN SEATBELT · S</button></div></div></div>}
      {safetyCleared && incident && incident.status === "ACTIVE" && <div role="alert" className="fixed right-5 top-5 z-50 w-[min(400px,calc(100vw-2rem))] rounded-xl border border-danger/70 bg-black/95 p-4 shadow-[0_0_35px_rgba(239,68,68,0.28)] backdrop-blur-xl"><div className="flex items-start gap-3"><div className="mt-1 h-3 w-3 shrink-0 rounded-full bg-danger shadow-[0_0_14px_rgba(239,68,68,0.9)]" /><div className="min-w-0 flex-1"><div className="num text-xs font-bold tracking-widest text-danger">MACHINE ALERT · {incident.severity}</div><div className="mt-1 text-sm font-semibold text-slate-100">{incident.incident_type.replace(/_/g, " ")}</div><p className="mt-2 text-xs leading-relaxed text-slate-300">{incident.recommended_action}</p>{incident.auto_reaction && <div className="mt-2 rounded border border-danger/40 bg-danger/10 px-2 py-1 num text-[10px] text-danger">AUTO RESPONSE: {incident.auto_reaction.replace(/_/g, " ")}</div>}</div></div></div>}
      {safetyCleared && taskNotice && taskNotice.next_task_type && (
        <div role="status" className="fixed bottom-5 left-20 z-40 w-[min(360px,calc(100vw-8rem))] rounded-xl border border-good/70 bg-black/90 p-4 shadow-[0_0_35px_rgba(52,211,153,0.25)] backdrop-blur-xl">
          <div className="flex items-start gap-3">
            <div className="mt-1 h-3 w-3 shrink-0 rounded-full bg-good shadow-[0_0_14px_rgba(52,211,153,0.9)]" />
            <div className="min-w-0 flex-1">
              <div className="num text-xs font-bold tracking-widest text-good">TASK COMPLETE</div>
              <div className="mt-1 text-sm font-semibold text-slate-100">{taskNotice.completed_task_type.replace(/_/g, " ")}</div>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">This task is marked done. Move to the next assignment on your shift plan.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => { clearTaskNotice(); onNavigate("tasks"); }}
                  className="rounded border border-good/60 bg-good/10 px-3 py-2 num text-[10px] font-semibold tracking-widest text-good"
                >
                  MOVE TO {taskNotice.next_task_type.replace(/_/g, " ")} →
                </button>
                <button onClick={clearTaskNotice} className="rounded border border-carbon-600 bg-carbon-800/50 px-3 py-2 num text-[10px] tracking-widest text-slate-300">
                  DISMISS
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
