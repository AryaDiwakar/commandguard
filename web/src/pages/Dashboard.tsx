import { useEffect, useRef, useState } from "react";

import { dashboardData, practiceCompare, resetDemo, startSession, whatIf } from "../lib/api";
import { launchScenario } from "../lib/scenario";
import type { DashboardData, PracticeComparison, WhatIfProjection } from "../lib/types";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

const riskTone = (risk: string) => risk === "CRITICAL" || risk === "HIGH" ? "text-danger" : risk === "MEDIUM" ? "text-warn" : "text-good";

export function DashboardPage() {
  const { machineId } = useTelemetry();
  const [data, setData] = useState<DashboardData | null>(null);
  const [projection, setProjection] = useState<WhatIfProjection | null>(null);
  const [practice, setPractice] = useState<PracticeComparison | null>(null);
  const [demoMessage, setDemoMessage] = useState("Waiting for live machine telemetry.");
  const autoStarted = useRef(false);

  const refresh = async () => {
    const result = await dashboardData(machineId).catch(() => null);
    if (result) setData(result);
    // Never leave the home page dark: if nothing is running, spin up a normal
    // shift automatically so telemetry populates immediately.
    if (result && !result.live && !autoStarted.current) {
      autoStarted.current = true;
      await startSession({ machine_id: machineId, speed: 5 }).catch(() => undefined);
      setDemoMessage("Live demo stream active.");
      refresh();
      return;
    }
    return result;
  };

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, [machineId]);

  const launch = async (scenario?: string) => {
    try {
      if (scenario) {
        const plan = await launchScenario(machineId, scenario, { severity: 0.85, onset_offset_s: 30, ramp_s: 8 });
        setDemoMessage(`Scenario staged. Degradation begins in T-${plan.waitSec}s; the safe-stop path is monitored live.`);
      } else {
        await startSession({ machine_id: machineId, speed: 5 });
        setDemoMessage("Live demo stream active.");
      }
      refresh();
    } catch {
      setDemoMessage("The current machine session could not be started.");
    }
  };

  const situation = data?.situation;
  const incident = data?.active_incidents[0];

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      <header className="glass-panel flex flex-wrap items-end justify-between gap-4 px-5 py-5">
        <div>
          <div className="hud-label text-cat">CAT COMMANDGUARD / YOUR SHIFT · {machineId}</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100 sm:text-3xl">The machine has a situation. You have a plan.</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            {incident ? `A ${incident.severity.toLowerCase()} incident needs attention.` : data?.live ? "The machine is working normally. Keep an eye on the live signals." : "Waiting for a live synthetic machine session."}
          </p>
        </div>
        <div className="num text-[10px] tracking-widest text-slate-400">{data?.live ? "RUNNING NOW" : "NO LIVE TELEMETRY"}</div>
      </header>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["HEALTH", situation?.machine_health ?? "—", "text-good"],
          ["RISK", situation?.current_risk ?? "—", riskTone(situation?.current_risk ?? "")],
          ["SHIFT LEFT", situation ? `${situation.shift_remaining_minutes.toFixed(1)}m` : data?.live ? "—" : "—", situation ? "text-cat" : "text-cat"],
          ["ACTIVE INCIDENTS", data?.active_incidents.length ?? "—", "text-danger"],
        ].map(([label, value, tone]) => <Panel key={String(label)}><div className="hud-label">{label}</div><div className={`mt-2 num text-2xl ${tone}`}>{value}</div></Panel>)}
      </div>

      <Panel title="BEFORE YOU WORK" right={<span className="num text-[10px] text-warn">{situation?.pre_shift_risk ?? "WAITING"} PRE-SHIFT RISK</span>}>
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="grid grid-cols-3 gap-3">
            <div><div className="hud-label">RISK SCORE</div><div className="mt-1 num text-2xl text-cat">{situation?.pre_shift_risk_score?.toFixed(0) ?? "—"}</div></div>
            <div><div className="hud-label">BEHAVIOR</div><div className="mt-1 num text-2xl text-holo">{situation?.behavior_score?.toFixed(0) ?? "—"}</div></div>
            <div><div className="hud-label">FATIGUE</div><div className="mt-1 text-sm text-slate-200">{situation?.fatigue_risk ?? "—"}</div></div>
          </div>
          <div className="flex flex-col gap-2">{(situation?.pre_shift_reasons ?? ["Waiting for live machine telemetry."]).map((reason) => <div key={reason} className="text-xs text-slate-400"><span className="mr-2 text-cat">•</span>{reason}</div>)}</div>
        </div>
        <div className="mt-4 flex flex-wrap gap-5 border-t border-carbon-700/60 pt-3 text-xs text-slate-500">
          <span>Practice: <b className="num text-holo">{situation?.productivity.recommended_practice ?? "—"}</b></span>
          <span>Output: <b className="num text-slate-200">{situation?.productivity.output_quantity?.toFixed(1) ?? "—"} {situation?.productivity.output_unit ?? ""}</b></span>
          <span>Efficiency: <b className="num text-good">{situation?.productivity.fuel_efficiency_output_per_l?.toFixed(2) ?? "—"}{situation ? " / L" : ""}</b></span>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="PRE-START BRIEF" right={<span className="num text-[10px] text-warn">{data?.pre_start.readiness ?? "LOADING"}</span>}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><div className="hud-label">CURRENT TASK</div><div className="mt-1 text-lg text-slate-100">{data?.current_task?.Task_Type ?? situation?.task ?? "—"}</div><div className="mt-1 text-xs text-slate-500">{data?.current_task?.Task_Zone ?? "—"}</div></div>
            <div><div className="hud-label">ENVIRONMENT</div><div className="mt-1 text-sm text-slate-300">{data?.pre_start.environment.terrain ?? "—"} · {data?.pre_start.environment.weather ?? "—"}</div><div className="mt-1 num text-xs text-slate-500">VIS {data?.pre_start.environment.visibility_m ?? "—"} m</div></div>
          </div>
          <div className="mt-4 flex flex-col gap-2">{data?.pre_start.focus.map((item) => <div key={item} className="flex gap-2 text-xs text-slate-400"><span className="text-holo">◈</span>{item}</div>)}</div>
        </Panel>
        <Panel title="PRACTICE CONTROLS" right={<span className="num text-[10px] text-danger">PRACTICE ONLY</span>}>
          <div className="grid gap-2">
            <button onClick={() => void launch()} className="rounded border border-holo/60 bg-holo/10 px-3 py-3 num text-xs tracking-widest text-holo">START NORMAL SHIFT</button>
            <button onClick={() => void launch("FUEL_LEAK")} className="rounded border border-danger/60 bg-danger/10 px-3 py-3 num text-xs tracking-widest text-danger">PRACTICE FUEL PROBLEM</button>
            <button onClick={() => { void resetDemo(); setDemoMessage("Demo reset. Waiting for a new live session."); refresh(); }} className="rounded border border-carbon-600 px-3 py-3 num text-xs tracking-widest text-slate-400">RESET PRACTICE</button>
          </div>
          <p className="mt-3 text-xs text-slate-500">{demoMessage}</p>
        </Panel>
      </div>

      <Panel title="WHAT-IF DECISION SUPPORT" right={<span className="num text-[10px] text-holo">GROUNDED PROJECTION</span>}>
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="grid grid-cols-3 gap-2">
            {(["CONTINUE", "REDUCE_LOAD", "STOP"] as const).map((action) => <button key={action} onClick={() => whatIf(machineId, action).then(setProjection).catch(() => undefined)} className="rounded border border-carbon-600 px-2 py-3 num text-[10px] text-slate-300">{action.replace("_", " ")}</button>)}
          </div>
          {projection ? <div className="rounded border border-carbon-700/70 bg-carbon-950/40 px-3 py-3 text-xs"><div className="flex flex-wrap gap-4 text-slate-500"><span>CURRENT <b className={riskTone(projection.current.risk)}>{projection.current.risk}</b></span><span>PROJECTED <b className={riskTone(projection.projection.risk)}>{projection.projection.risk}</b></span><span>ETA <b className="text-cat">{projection.projection.eta_minutes.toFixed(1)}m</b></span></div><p className="mt-2 text-slate-300">{projection.projection.message}</p><div className="mt-2 text-[10px] text-slate-500">Assumptions: {projection.assumptions.join(" · ")}</div></div> : <div className="py-3 text-sm text-slate-500">Compare the consequence of continuing, reducing load, or stopping from the current machine state.</div>}
        </div>
      </Panel>

      <Panel title="PRACTICE LAB" right={<span className="num text-[10px] text-cat">PRODUCTIVITY + SAFETY</span>}>
        <div className="flex flex-wrap items-center justify-between gap-3"><p className="max-w-2xl text-xs text-slate-500">Compare operating styles against the current live machine context.</p><button onClick={() => practiceCompare(machineId).then(setPractice).catch(() => undefined)} className="rounded border border-cat/60 bg-cat/10 px-3 py-2 num text-[10px] tracking-widest text-cat">COMPARE PRACTICES</button></div>
        {practice && <div className="mt-4 grid gap-2 md:grid-cols-4">{practice.comparisons.map((item) => <div key={item.profile} className="rounded border border-carbon-700/70 bg-carbon-950/30 px-3 py-3"><div className="flex justify-between"><span className="num text-xs text-slate-100">{item.profile.replace(/_/g, " ")}</span><span className={"num text-[10px] " + riskTone(item.risk)}>{item.risk}</span></div><div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-slate-500"><span>TIME <b className="num text-slate-200">{item.task_time_minutes}m</b></span><span>FUEL <b className="num text-slate-200">{item.fuel_liters}L</b></span><span>OUTPUT/MIN <b className="num text-holo">{item.output_per_minute}</b></span><span>SCORE <b className="num text-cat">{item.score}</b></span></div></div>)}</div>}
      </Panel>
    </div>
  );
}
