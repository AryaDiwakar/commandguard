import type { MachineSituation, TaskSchedule } from "../lib/types";
import { Panel } from "./Panel";
import { ScenarioLab } from "./ScenarioLab";

export function OperationalContext({
  situation,
  tasks,
  machineId,
}: {
  situation: MachineSituation | null;
  tasks: TaskSchedule[];
  machineId: string;
}) {
  const currentTask = tasks[0];

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_1.35fr_1fr]">
      <Panel title="TASK VECTOR" right={<span className="num text-[10px] text-holo">SCHEDULED</span>}>
        <div className="grid grid-cols-2 gap-3">
          <div><div className="hud-label">CURRENT TASK</div><div className="mt-1 num text-lg text-slate-100">{situation?.task ?? currentTask?.Task_Type ?? "—"}</div></div>
          <div><div className="hud-label">PROGRESS</div><div className="mt-1 num text-lg text-holo">{situation ? `${situation.task_progress_pct.toFixed(1)}%` : "—"}</div></div>
          <div><div className="hud-label">DYNAMIC ETA</div><div className="mt-1 num text-lg text-cat">{situation?.eta_minutes.toFixed(1) ?? "—"} min</div></div>
          <div><div className="hud-label">BASELINE</div><div className="mt-1 num text-lg text-slate-300">{situation?.eta_baseline_minutes.toFixed(1) ?? "—"} min</div></div>
        </div>
        {situation?.eta_reasons.length ? <div className="mt-3 text-[11px] text-warn">ETA drivers: {situation.eta_reasons.join(" · ")}</div> : <div className="mt-3 text-[11px] text-slate-500">ETA is adapting to telemetry, environment, and machine condition.</div>}
      </Panel>

      <Panel title="PREDICTIVE RISK" right={<span className="num text-[10px] text-warn">FORWARD LOOK</span>}>
        {situation?.predicted_risks.length ? (
          <div className="flex flex-col gap-2">
            {situation.predicted_risks.map((risk) => (
              <div key={risk.type} className="rounded border border-warn/30 bg-warn/5 px-3 py-2">
                <div className="flex items-center justify-between"><span className="num text-xs text-warn">{risk.type.replace(/_/g, " ")}</span><span className="num text-[10px] text-slate-400">{risk.time_to_threshold_min.toFixed(1)} MIN</span></div>
                <div className="mt-1 text-xs text-slate-300">{risk.message}</div>
              </div>
            ))}
          </div>
        ) : <div className="py-3 text-sm text-slate-500">No immediate trajectory risk. Trend engine is monitoring the next operating window.</div>}
        {situation?.early_warnings.length ? <div className="mt-3 border-t border-carbon-700/60 pt-3"><div className="hud-label text-warn">EARLY SIGNALS</div>{situation.early_warnings.map((warning) => <div key={warning.signal} className="mt-2 text-xs text-warn">{warning.message} <span className="num text-slate-500">z={warning.z_score.toFixed(1)}</span></div>)}</div> : null}
      </Panel>

      <Panel title="SCENARIO LAB" right={<span className="num text-[10px] text-danger">SIMULATION ONLY</span>}>
        <div className="text-xs leading-relaxed text-slate-500">Inject a gradual defect into the live synthetic stream. Auto safety override engages on the critical tier.</div>
        <div className="mt-3"><ScenarioLab machineId={machineId} compact /></div>
      </Panel>
    </div>
  );
}
