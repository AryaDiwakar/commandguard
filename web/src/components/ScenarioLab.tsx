import { useEffect, useRef, useState } from "react";

import { liveSituation, operatorInput, requestHelp, scenarioCatalog, sendOperatorAction } from "../lib/api";
import { DEFAULT_ONSET_S, DEFAULT_SEVERITY, incidentMatchesScenario, launchScenario, phaseFromIncident, type ScenarioPhase } from "../lib/scenario";
import type { Incident, ScenarioOption, TelemetryFrame } from "../lib/types";
import { useTelemetry } from "../store/useTelemetry";

const STEPS: Array<{ phase: ScenarioPhase; label: string; chip: string }> = [
  { phase: "staged", label: "STAGED", chip: "border-warn/60 bg-warn/15 text-warn" },
  { phase: "monitoring", label: "MONITORING", chip: "border-warn/60 bg-warn/15 text-warn" },
  { phase: "detected", label: "DETECTED", chip: "border-warn/60 bg-warn/15 text-warn" },
  { phase: "override", label: "AUTO SAFETY OVERRIDE", chip: "border-danger/60 bg-danger/15 text-danger" },
  { phase: "secured", label: "SECURED", chip: "border-good/60 bg-good/15 text-good" },
];

function phaseChip(phase: ScenarioPhase): string {
  switch (phase) {
    case "armed":
      return "border-holo/50 bg-holo/10 text-holo";
    case "secured":
      return "border-good/50 bg-good/10 text-good";
    case "override":
      return "border-danger/60 bg-danger/10 text-danger";
    default:
      return "border-warn/50 bg-warn/10 text-warn";
  }
}

export function ScenarioLab({
  machineId,
  compact = false,
  explain = "Scenario labels are written into the stream plan but never leaked to the operator intelligence path.",
}: {
  machineId: string;
  compact?: boolean;
  explain?: string;
}) {
  const [scenarios, setScenarios] = useState<ScenarioOption[]>([]);
  const [selected, setSelected] = useState("FUEL_LEAK");
  const [busy, setBusy] = useState(false);
  const [launched, setLaunched] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [incident, setIncident] = useState<Incident | null>(null);
  const [frame, setFrame] = useState<TelemetryFrame | null>(null);
  const [fuelStart, setFuelStart] = useState<number | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [launchedType, setLaunchedType] = useState<string | null>(null);
  const { setScenarioType, setIncident: setGlobalIncident } = useTelemetry();
  const countdownRef = useRef(0);
  const previousIncident = useRef<string | null>(null);
  const phase: ScenarioPhase = launched
    ? countdown > 0
      ? "staged"
      : phaseFromIncident(incident)
    : "armed";

  useEffect(() => {
    scenarioCatalog()
      .then((result) => {
        setScenarios(result.scenarios);
        if (result.scenarios.length > 0) setSelected(result.scenarios[0].type);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!launched) return undefined;
    const timer = window.setInterval(() => {
      liveSituation(machineId)
        .then((state) => {
          if (state.frame) {
            setFrame(state.frame);
            setFuelStart((current) => current ?? state.frame!.fuel_level_pct);
          }
          const active = (state.situation?.active_incidents ?? []) as Incident[];
          const matching = active.filter((item) => incidentMatchesScenario(item.incident_type, launchedType ?? selected));
          const nextIncident = matching.find((item) => item.auto_reaction || item.response_status === "VERIFIED") ?? matching[0] ?? null;
          setWarning(state.situation?.predicted_risks[0]?.message ?? null);
          if (nextIncident && nextIncident.incident_id !== previousIncident.current) {
          }
          previousIncident.current = nextIncident?.incident_id ?? previousIncident.current;
          setIncident(nextIncident);
          setGlobalIncident(nextIncident);
        })
        .catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [launched, launchedType, machineId, selected, setGlobalIncident]);

  const simulate = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      const plan = await launchScenario(machineId, selected, {
        severity: DEFAULT_SEVERITY,
        onset_offset_s: DEFAULT_ONSET_S,
        ramp_s: 8,
      });
      setLaunched(true);
      setError(null);
      setLaunchedType(selected);
      setScenarioType(selected);
      setIncident(null);
      setFrame(null);
      setFuelStart(null);
      setWarning(null);
      previousIncident.current = null;
      setCountdown(plan.waitSec);
      countdownRef.current = plan.waitSec;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Scenario could not be started.");
      setLaunched(false);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (countdown <= 0) return undefined;
    const timer = window.setTimeout(() => {
      countdownRef.current = Math.max(0, countdownRef.current - 1);
      setCountdown(countdownRef.current);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [countdown]);

  const tone = phaseChip(phase);
  const headline =
    phase === "staged"
      ? `Degradation injecting in T-${Math.max(0, countdown)}s …`
      : phase === "detected"
        ? "Defect detected. The system is holding the escalation window open."
        : phase === "override"
          ? incident?.auto_reaction_reason ?? "Conditions crossed the critical tier, so the machine was overridden to a safe stop."
          : phase === "secured"
            ? "Telemetry confirms the machine is secured and the simulated leak source is contained. Response verified."
            : "Select a script to stage a live synthetic defect.";

  const selector = compact ? (
    <div className="flex gap-2">
      <select value={selected} onChange={(event) => setSelected(event.target.value)} className="min-w-0 flex-1 rounded border border-carbon-600/70 bg-carbon-800 px-2 py-2 num text-[11px] text-slate-200 outline-none focus:border-holo">
        {scenarios.map((scenario) => <option key={scenario.type} value={scenario.type}>{scenario.label}</option>)}
      </select>
      <button onClick={() => void simulate()} disabled={busy || scenarios.length === 0} className="rounded border border-danger/60 bg-danger/10 px-3 py-2 num text-[10px] font-semibold tracking-widest text-danger transition hover:bg-danger/20 disabled:cursor-wait disabled:opacity-50">{busy ? "BOOTING" : "SIMULATE"}</button>
    </div>
  ) : (
    <div className="grid gap-2 sm:grid-cols-2">
      {scenarios.map((scenario) => (
        <button key={scenario.type} onClick={() => setSelected(scenario.type)} className={"rounded border px-3 py-3 text-left transition " + (selected === scenario.type ? "border-signal/70 bg-signal/10" : "border-carbon-700/70 bg-carbon-950/30 hover:border-carbon-500")}>
          <div className="num text-xs text-slate-100">{scenario.label}</div>
          <div className="mt-1 text-[10px] text-slate-500">Onset {String(scenario.default_plan.onset_offset_s)}s · severity {DEFAULT_SEVERITY} · ramp 8s</div>
        </button>
      ))}
    </div>
  );

  return (
    <div className="grid gap-4">
      {!compact && <p className="text-xs leading-relaxed text-slate-500">{explain}</p>}
      {selector}
      {error && <div className="rounded border border-danger/50 bg-danger/10 px-3 py-2 text-xs text-danger">{error}</div>}
      {launched && <div className="grid grid-cols-2 gap-2 rounded border border-carbon-700/70 bg-carbon-950/40 px-3 py-3 sm:grid-cols-4">
        <div><div className="hud-label">FUEL LEVEL</div><div className="mt-1 num text-lg text-signal">{frame ? `${frame.fuel_level_pct.toFixed(2)}%` : "—"}</div></div>
        <div><div className="hud-label">FUEL DELTA</div><div className={"mt-1 num text-lg " + (frame && fuelStart !== null && frame.fuel_level_pct < fuelStart ? "text-danger" : "text-slate-200")}>{frame && fuelStart !== null ? `${(frame.fuel_level_pct - fuelStart).toFixed(2)}%` : "—"}</div></div>
        <div className="col-span-2 text-xs text-slate-400">{warning ?? "Waiting for observed degradation telemetry."}</div>
      </div>}
      <div className="rounded border border-carbon-700/70 bg-carbon-950/40 px-3 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="hud-label">{selected.replace(/_/g, " ") ?? "SCENARIO"}</div>
          <span className={"rounded-full border px-2 py-0.5 num text-[10px] tracking-widest " + tone}>{phase.toUpperCase()}</span>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-slate-300">{headline}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {STEPS.map((step) => {
            const activeIdx = STEPS.findIndex((s) => s.phase === phase);
            const stepIdx = STEPS.findIndex((s) => s.phase === step.phase);
            const reached = launched && phase !== "armed" && stepIdx <= activeIdx;
            return (
              <span key={step.phase} className={"rounded border px-2 py-1 num text-[9px] tracking-widest " + (reached && step.phase === phase ? step.chip : reached ? "border-carbon-600 bg-carbon-800 text-slate-400" : "border-carbon-700/70 text-slate-600")}>
                {step.label}
              </span>
            );
          })}
        </div>
        {phase === "override" && incident?.auto_reaction && <div className="mt-3 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">Action taken: {incident.auto_reaction.replace(/_/g, " ")} — no operator input required.</div>}
        {incident && <div className="mt-3 grid gap-2 rounded border border-danger/50 bg-danger/10 p-3">
          <div className="text-xs font-semibold text-danger">{incident.incident_type.replace(/_/g, " ")} CONFIRMED</div>
          <div className="text-xs text-slate-300">{incident.recommended_action}</div>
          <div className="flex flex-wrap gap-2">
            {incident.help_status === "NOT_REQUESTED" && <button onClick={() => requestHelp(machineId, incident.incident_id).then((result) => { setIncident(result.relay); setGlobalIncident(result.relay); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Help request failed."))} className="rounded border border-signal/60 bg-signal/10 px-3 py-2 num text-[10px] tracking-widest text-signal">REQUEST LIVE ASSISTANCE</button>}
            {incident.status !== "RESOLVED" && <button onClick={() => sendOperatorAction(machineId, "STOP_MACHINE", incident.incident_id).then((result) => { setIncident(result.incident); setGlobalIncident(result.incident); }).catch(() => undefined)} className="rounded border border-danger/60 bg-danger/10 px-3 py-2 num text-[10px] tracking-widest text-danger">STOP MACHINE SAFELY</button>}
          </div>
        </div>}
        {!incident && warning && <button onClick={() => operatorInput(machineId, "STOP_MACHINE").catch(() => undefined)} className="mt-3 rounded border border-danger/60 bg-danger/10 px-3 py-2 num text-[10px] tracking-widest text-danger">STOP MACHINE FROM EARLY WARNING</button>}
        {phase === "secured" && <div className="mt-3 text-[10px] text-slate-500">The safe stop contains the simulated hazard; maintenance would still be required to repair the machine. Engine shutdown remains operator-controlled.</div>}
      </div>
    </div>
  );
}
