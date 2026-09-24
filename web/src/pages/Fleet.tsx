import { useEffect, useState } from "react";

import { fleetOverview, bootFleet } from "../lib/api";
import { Panel } from "../components/Panel";
import { LiveIndicator } from "../components/LiveIndicator";

type FleetMachine = Awaited<ReturnType<typeof fleetOverview>>["machines"][number];

const tone = (value: string) => value === "HIGH" || value === "CRITICAL" ? "text-danger" : value === "MEDIUM" ? "text-warn" : value === "LOW" || value === "HEALTHY" ? "text-good" : "text-slate-400";

export function FleetPage({ onOpenMachine }: { onOpenMachine: (machineId: string) => void }) {
  const [machines, setMachines] = useState<FleetMachine[]>([]);
  const refresh = () => fleetOverview().then((result) => setMachines(result.machines)).catch(() => undefined);
  useEffect(() => {
    bootFleet().catch(() => undefined); // deterministic fleet boot — idempotent, skips already-running sessions
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      <header className="glass-panel px-5 py-5">
        <div className="hud-label text-cat">SUPERVISOR VIEW / FLEET</div>
        <h1 className="mt-1 text-2xl font-semibold text-slate-100">Every machine. One clear picture.</h1>
        <p className="mt-2 text-sm text-slate-500">Health, risk, operator behavior, fatigue, task time, and active incidents across the synthetic site.</p>
      </header>
      <div className="grid gap-4 lg:grid-cols-3">
        {machines.map((machine) => (
          <div
            key={machine.machine_id}
            onClick={() => onOpenMachine(machine.machine_id)}
            className="cursor-pointer transition hover:brightness-110"
            title="Open live machine screen"
          >
            <Panel
              title={machine.machine_id}
              right={<LiveIndicator live={machine.live} />}
            >
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300">{machine.model} · {machine.site}</span>
              <span className="num text-[10px] tracking-widest text-holo">OPEN LIVE ▲</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div><div className="hud-label">HEALTH</div><div className={"mt-1 text-sm " + tone(machine.machine_health)}>{machine.machine_health}</div></div>
              <div><div className="hud-label">RISK</div><div className={"mt-1 text-sm " + tone(machine.current_risk)}>{machine.current_risk}</div></div>
              <div><div className="hud-label">BEHAVIOR</div><div className="mt-1 num text-sm text-holo">{machine.behavior_score?.toFixed(0) ?? "—"}</div></div>
              <div><div className="hud-label">FATIGUE</div><div className={"mt-1 text-sm " + tone(machine.fatigue_risk)}>{machine.fatigue_risk}</div></div>
            </div>
            <div className="mt-4 flex items-center justify-between rounded border border-carbon-700/60 bg-carbon-950/30 px-3 py-2 text-xs">
              <span className="text-slate-300">{machine.task ?? "No task"}</span>
              {machine.eta_minutes !== null && <span className="num text-cat">{machine.eta_minutes.toFixed(1)}m</span>}
            </div>
            {machine.active_incidents.length > 0 && (
              <div className="mt-3 text-xs text-danger">{machine.active_incidents.length} active incident(s) require attention.</div>
            )}
            </Panel>
          </div>
        ))}
      </div>
    </div>
  );
}
