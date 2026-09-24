import { useEffect, useState } from "react";

import { liveSituation, todayTasks } from "../lib/api";
import type { TaskSchedule, TodayTasksResponse } from "../lib/types";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

export function TasksPage() {
  const [tasks, setTasks] = useState<TaskSchedule[]>([]);
  const [meta, setMeta] = useState<TodayTasksResponse["eta_model"] | null>(null);
  const [filter, setFilter] = useState<string>("ALL");
  const { machineId, situation, latest, pushFrames, setSituation } = useTelemetry();

  useEffect(() => {
    setTasks([]);
    setMeta(null);
    todayTasks(machineId)
      .then((result) => {
        setTasks(result.tasks);
        setMeta(result.eta_model);
      })
      .catch(() => undefined);
  }, [machineId]);

  // Keep the live task ETA / progress fresh on the schedule page so the
  // ACTIVE TASK ETA reflects the running machine instead of a static model.
  useEffect(() => {
    const timer = window.setInterval(() => {
      liveSituation(machineId)
        .then((state) => {
          if (state.frame) pushFrames([state.frame]);
          if (state.situation) setSituation(state.situation);
        })
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [machineId, pushFrames, setSituation]);

  const totalEstimate = tasks.reduce((sum, t) => sum + t.Estimated_Time_min, 0);
  const currentIdx = situation ? Math.min(Math.max(0, situation.task_index), Math.max(0, tasks.length - 1)) : 0;
  const activeTask = tasks.find((task) => task.Task_Type === situation?.task) ?? tasks[currentIdx] ?? tasks[0];

  const filteredTasks = tasks.filter((t) => {
    if (filter === "CRITICAL") return t.Task_Priority === "CRITICAL";
    if (filter === "HIGH") return t.Task_Priority === "HIGH" || t.Task_Priority === "CRITICAL";
    return true;
  });

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      {/* Dashboard Header */}
      <header className="glass-panel flex flex-wrap items-end justify-between gap-4 px-5 py-5">
        <div>
          <div className="hud-label text-holo">DAILY TASK DASHBOARD · {machineId}</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100 sm:text-3xl">Scheduled Tasks for the Day</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">
            Real-time work vector for {machineId}. Combines scheduled task assignments with the trained ETA model{meta ? ` (${meta.model_name})` : ""} and live environmental modifiers.
          </p>
        </div>
        <div className="num text-right text-xs text-slate-400">
          <div className="text-2xl text-slate-100">{tasks.length}</div>
          TASKS ASSIGNED TODAY
        </div>
      </header>

      {/* KPI Overview Row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Panel>
          <div className="hud-label">TOTAL TASKS</div>
          <div className="mt-2 num text-3xl text-slate-100">{tasks.length}</div>
          <div className="mt-1 text-xs text-slate-500">{situation ? `${currentIdx + 1} of ${situation.task_count} in progress · ${Math.max(0, tasks.length - currentIdx - 1)} upcoming` : "Waiting for live task telemetry"}</div>
        </Panel>
        <Panel>
          <div className="hud-label">TOTAL SHIFT TIME</div>
          <div className="mt-2 num text-3xl text-holo">{tasks.length ? `${(totalEstimate / 60).toFixed(1)} ` : "— "}<span className="text-sm text-slate-500">{tasks.length ? "hrs" : ""}</span></div>
          <div className="mt-1 text-xs text-slate-500">{tasks.length ? `~${totalEstimate.toFixed(0)} mins scheduled load` : "No schedule loaded"}</div>
        </Panel>
        <Panel>
          <div className="hud-label">ACTIVE TASK ETA</div>
          <div className="mt-2 num text-3xl text-cat">
            {situation ? `${situation.eta_minutes.toFixed(1)}m` : activeTask?.model_predicted_min != null ? `${activeTask.model_predicted_min.toFixed(1)}m` : "—"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Planned: {situation?.eta_baseline_minutes.toFixed(1) ?? (activeTask ? activeTask.Estimated_Time_min.toFixed(1) : "—")} min
          </div>
        </Panel>
        <Panel>
          <div className="hud-label">ENV RISK MODIFIER</div>
          <div className="mt-2 num text-3xl text-good">
            {situation?.eta_reasons.length ? `+${(situation.eta_reasons.length * 10)}%` : "NOMINAL"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {situation?.eta_reasons.length ? situation.eta_reasons.join(", ") : "Standard weather & terrain"}
          </div>
        </Panel>
      </div>

      {/* Task Time Estimation (ML Model & Dynamic Prediction) */}
      <Panel
        title="TASK TIME ESTIMATION / ML DYNAMIC PREDICTOR"
        right={meta ? <span className="num text-[10px] text-good">TRAINED ON {meta.training_rows.toLocaleString()} TASK ROWS</span> : <span className="num text-[10px] text-good">TRAINED ON 90-DAY TASK HISTORY</span>}
      >
        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">How Task Completion Time is Predicted:</h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              Predictions combine historical synthetic work cycles, operator efficiency, and machine age with real-time site conditions. Unlike static schedules, this model dynamically penalizes weather, slippery terrain, and machine distress.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-2.5">
                <div className="hud-label">HISTORICAL BASELINE</div>
                <div className="mt-1 num text-base text-slate-200">
                  {situation?.eta_baseline_minutes.toFixed(1) ?? activeTask?.Estimated_Time_min.toFixed(1) ?? "—"} m
                </div>
                <div className="text-[10px] text-slate-500">Standard cycle time</div>
              </div>
              <div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-2.5">
                <div className="hud-label">WEATHER PENALTY</div>
                <div className="mt-1 num text-base text-holo">
                  {latest ? latest.rainfall_mmh > 0 ? `+${(latest.rainfall_mmh / 4).toFixed(0)}%` : "0%" : "—"}
                </div>
                <div className="text-[10px] text-slate-500">{latest?.weather_event ?? "—"}</div>
              </div>
              <div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-2.5">
                <div className="hud-label">TERRAIN FACTOR</div>
                <div className="mt-1 num text-base text-cat">
                  {latest ? latest.terrain_condition === "MUDDY" ? "+18%" : latest.terrain_condition === "WET" ? "+8%" : "0%" : "—"}
                </div>
                <div className="text-[10px] text-slate-500">{latest?.terrain_condition ?? "—"}</div>
              </div>
              <div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-2.5">
                <div className="hud-label">MODEL MAE</div>
                <div className="mt-1 num text-base text-good">±{meta?.holdout_mae_minutes.toFixed(1) ?? "—"} min</div>
                <div className="text-[10px] text-slate-500">{meta ? `Holdout · RMSE ±${meta.holdout_rmse_minutes.toFixed(1)}` : "Holdout evaluated"}</div>
              </div>
            </div>
          </div>
          <div className="flex flex-col justify-center rounded border border-holo/20 bg-holo/5 p-4">
            <div className="hud-label text-holo">CURRENT TASK VECTOR</div>
            <div className="mt-1 text-lg font-semibold text-slate-100">{activeTask?.Task_Type ?? situation?.task ?? "—"}</div>
            <div className="mt-1 text-xs text-slate-400">Zone: {activeTask?.Task_Zone ?? latest?.work_zone ?? "—"} · Machine {machineId}</div>
            <div className="mt-3 flex items-center justify-between text-xs">
              <span className="text-slate-400">Task Progress</span>
              <span className="num text-holo">{situation?.task_progress_pct.toFixed(1) ?? "—"}{situation ? "%" : ""}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-carbon-800">
              <div
                className="h-full bg-gradient-to-r from-holo-dark to-holo"
                style={{ width: `${situation?.task_progress_pct ?? 0}%` }}
              />
            </div>
          </div>
        </div>
      </Panel>

      {/* Scheduled Tasks List & Filter */}
      <Panel
        title="TODAY'S SCHEDULED WORK PLAN"
        right={
          <div className="flex gap-1">
            {["ALL", "CRITICAL", "HIGH"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={
                  "rounded px-2 py-0.5 num text-[10px] tracking-wider transition " +
                  (filter === f ? "border border-holo/40 bg-holo/10 text-holo" : "text-slate-500 hover:text-slate-300")
                }
              >
                {f}
              </button>
            ))}
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="hud-label border-b border-carbon-700/70">
              <tr>
                <th className="px-3 py-3">STATUS</th>
                <th>TASK ID</th>
                <th>TYPE</th>
                <th>ZONE</th>
                <th>WEATHER</th>
                <th>TERRAIN</th>
                <th>ESTIMATED TIME</th>
                <th>ML PREDICTED</th>
                <th>PRIORITY</th>
              </tr>
            </thead>
            <tbody>
              {filteredTasks.map((task, idx) => {
                const isCompleted = situation ? idx < situation.task_index : false;
                const isCurrent = idx === currentIdx;
                return (
                  <tr
                    key={task.Task_ID}
                    className={"border-b border-carbon-800/80 transition " + (isCurrent ? "bg-holo/5 text-slate-100" : "text-slate-300 hover:bg-carbon-900/50") + (isCompleted ? " opacity-70" : "")}
                  >
                    <td className="px-3 py-3">
                      <span
                        className={
                          "rounded-full px-2 py-0.5 num text-[9px] " +
                          (isCompleted
                            ? "border border-good/40 bg-good/10 text-good"
                            : isCurrent
                            ? "border border-holo/50 bg-holo/15 text-holo"
                            : "border border-carbon-600 bg-carbon-800 text-slate-400")
                        }
                      >
                        {isCompleted ? "✓ COMPLETED" : isCurrent ? "● IN PROGRESS" : "UPCOMING"}
                      </span>
                    </td>
                    <td className="num font-semibold text-holo">{task.Task_ID}</td>
                    <td className="font-medium text-slate-200">{task.Task_Type}</td>
                    <td className="num text-slate-400">{task.Task_Zone}</td>
                    <td>{task.Weather}</td>
                    <td>{task.Terrain_Condition}</td>
                    <td className="num text-slate-300">{task.Estimated_Time_min.toFixed(1)} min</td>
                    <td className="num text-cat font-medium">
                      {task.model_predicted_min != null ? `${task.model_predicted_min.toFixed(1)} min` : "—"}
                    </td>
                    <td>
                      <span className={"num text-[10px] " + (task.Task_Priority === "CRITICAL" ? "text-danger" : task.Task_Priority === "HIGH" ? "text-warn" : "text-slate-400")}>
                        {task.Task_Priority}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
