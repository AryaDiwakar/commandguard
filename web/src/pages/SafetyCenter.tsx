import { useEffect, useState } from "react";

import { safetyProcedures } from "../lib/api";
import type { SafetyProcedure } from "../lib/types";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

export function SafetyCenterPage() {
  const [procedures, setProcedures] = useState<SafetyProcedure[]>([]);
  const { latest, situation } = useTelemetry();

  useEffect(() => {
    safetyProcedures().then((result) => setProcedures(result.procedures)).catch(() => undefined);
  }, []);

  const f = latest;
  const sit = situation;
  const noSignal = !f;

  // Real-time Safety Calculations
  const seatbeltFastened = f?.Seatbelt_Status === "Fastened";
  const machineMoving = (f?.machine_speed_kph ?? 0) > 0.1;
  const seatbeltViolation = !!f && !seatbeltFastened && machineMoving;

  const proximityDist = f?.proximity_distance_m;
  const proximityHazard = !!f && (proximityDist ?? 99) < 8.0 && machineMoving;

  const idlingMin = f?.Idling_Time_min;
  const excessiveIdle = !!f && (idlingMin ?? 0) >= 4.0;

  const vibration = f?.vibration_g;
  const aggression = f?.aggression_index;
  const speed = f?.machine_speed_kph ?? 0;
  const unsafeOperation = !!f && (((vibration ?? 0) > 0.9 && (aggression ?? 0) > 0.45) || speed > 12.5);
  const alertActive = seatbeltViolation || proximityHazard || unsafeOperation;

  const weather = f?.weather_event;
  const rainfall = f?.rainfall_mmh;
  const visibility = f?.visibility_m;
  const terrain = f?.terrain_condition;
  const slope = f?.slope_deg;

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      {/* Header */}
      <header className="glass-panel flex flex-wrap items-end justify-between gap-4 px-5 py-5">
        <div>
          <div className="hud-label text-good">REAL-TIME SAFETY CENTER / OPERATOR COMPLIANCE</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100 sm:text-3xl">Safety Features & Live Monitoring</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">
            Continuous real-time operator protection: seatbelt compliance, proximity radar, working conditions, and unusual usage patterns.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={"h-2.5 w-2.5 rounded-full " + (noSignal ? "bg-slate-600" : alertActive ? "bg-danger animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.9)]" : "bg-good shadow-[0_0_12px_rgba(34,197,94,0.9)]")} />
          <span className="num text-xs tracking-widest text-slate-300">
            {noSignal ? "NO LIVE TELEMETRY" : alertActive ? "SAFETY ALERTS ACTIVE" : "ALL SYSTEMS SAFE"}
          </span>
        </div>
      </header>

      {/* Real-time Safety Features Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* 1. Seatbelt Compliance */}
        <Panel
          title="1. SEATBELT COMPLIANCE"
          right={
            <span className={"num text-[10px] " + (noSignal ? "text-slate-500" : seatbeltViolation ? "text-danger" : seatbeltFastened ? "text-good" : "text-warn")}>
              {noSignal ? "NO SIGNAL" : seatbeltViolation ? "VIOLATION" : seatbeltFastened ? "FASTENED" : "UNFASTENED"}
            </span>
          }
          className={seatbeltViolation ? "border-danger/70 shadow-[0_0_20px_rgba(239,68,68,0.15)]" : undefined}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className={"text-3xl " + (noSignal ? "text-slate-500" : seatbeltViolation ? "text-danger" : seatbeltFastened ? "text-good" : "text-warn")}>
                {noSignal ? "—" : seatbeltFastened ? "🔒" : "⚠️"}
              </span>
              <div>
                <div className="num text-lg font-semibold text-slate-100">
                  {noSignal ? "—" : (f?.Seatbelt_Status ?? "—")}
                </div>
                <div className="text-[11px] text-slate-500">
                  {noSignal ? "No live frame" : machineMoving ? `Moving at ${speed.toFixed(1)} km/h` : "Stationary"}
                </div>
              </div>
            </div>
            <div className={"rounded border px-2 py-1 num text-[10px] " + (noSignal ? "border-slate-600 bg-carbon-900 text-slate-400" : seatbeltViolation ? "border-danger/60 bg-danger/10 text-danger" : "border-good/50 bg-good/10 text-good")}>
              {noSignal ? "NO SIGNAL" : seatbeltViolation ? "STOP & FASTEN" : "COMPLIANT"}
            </div>
          </div>
          <div className="mt-3 text-xs leading-relaxed text-slate-400">
            {noSignal
              ? "Waiting for live telemetry from CommandGuard sensors."
              : seatbeltViolation
              ? "CRITICAL: Seatbelt unbuckled while machine is moving! Movement interlock triggered."
              : "Safety interlock active. Operator restraint confirmed engaged before movement."}
          </div>
        </Panel>

        {/* 2. Proximity Hazards */}
        <Panel
          title="2. PROXIMITY HAZARDS"
          right={
            <span className={"num text-[10px] " + (noSignal ? "text-slate-500" : proximityHazard ? "text-danger" : (proximityDist ?? 99) < 12 ? "text-warn" : "text-good")}>
              {noSignal ? "—" : `${proximityDist!.toFixed(1)}m RANGE`}
            </span>
          }
          className={proximityHazard ? "border-danger/70 shadow-[0_0_20px_rgba(239,68,68,0.15)]" : undefined}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="hud-label">NEAREST OBSTACLE</div>
              <div className={"mt-1 num text-2xl " + (noSignal ? "text-slate-500" : proximityHazard ? "text-danger" : (proximityDist ?? 99) < 12 ? "text-warn" : "text-good")}>
                {noSignal ? "—" : `${proximityDist!.toFixed(1)}`} {noSignal ? "" : <span className="text-xs text-slate-500">meters</span>}
              </div>
            </div>
            <div className="text-right">
              <div className="hud-label">ASSETS IN ZONE</div>
              <div className="mt-1 num text-xl text-holo">{f?.nearby_machine_count ? f.nearby_machine_count : "—"}</div>
            </div>
          </div>
          {/* Radar bar */}
          <div className="mt-3">
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>0m DANGER</span>
              <span>8m SAFE BOUNDARY</span>
              <span>25m</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-carbon-800">
              <div
                className={"h-full transition-all " + (noSignal ? "bg-slate-700" : (proximityDist ?? 99) < 8 ? "bg-danger" : (proximityDist ?? 99) < 12 ? "bg-warn" : "bg-good")}
                style={{ width: `${noSignal ? 0 : Math.min(100, ((proximityDist ?? 0) / 25) * 100)}%` }}
              />
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {noSignal ? "Proximity radar standing by for telemetry." : proximityHazard ? "COLLISION WARNING: Obstacle inside 8m radius while moving!" : "Work zone clear. Proximity radar actively scanning."}
          </div>
        </Panel>

        {/* 3. Unusual Usage: Excessive Idling */}
        <Panel
          title="3. EXCESSIVE IDLING"
          right={
            <span className={"num text-[10px] " + (noSignal ? "text-slate-500" : excessiveIdle ? "text-warn" : "text-good")}>
              {noSignal ? "NO SIGNAL" : excessiveIdle ? "IDLE EXCEEDED" : "NORMAL"}
            </span>
          }
        >
          <div className="flex items-baseline justify-between">
            <div>
              <div className="hud-label">CURRENT IDLE TIME</div>
              <div className={"mt-1 num text-2xl " + (noSignal ? "text-slate-500" : excessiveIdle ? "text-warn" : "text-slate-100")}>
                {noSignal ? "—" : `${(idlingMin ?? 0).toFixed(1)}`} {noSignal ? "" : <span className="text-xs text-slate-500">min</span>}
              </div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div>Limit: 4.0 min</div>
              <div className="num text-signal mt-0.5">{noSignal ? "—" : `~${((idlingMin ?? 0) * 0.05).toFixed(2)} L wasted`}</div>
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-carbon-800">
            <div
              className={"h-full transition-all " + (noSignal ? "bg-slate-700" : (idlingMin ?? 0) >= 4 ? "bg-warn" : "bg-holo")}
              style={{ width: `${noSignal ? 0 : Math.min(100, ((idlingMin ?? 0) / 6.0) * 100)}%` }}
            />
          </div>
          <div className="mt-2 text-xs text-slate-400">
            {noSignal
              ? "Idle monitor waiting for telemetry."
              : excessiveIdle
              ? "Machine has idled over 4 mins without operational task. Shut down engine to conserve fuel."
              : "Idling duration is within standard operational threshold."}
          </div>
        </Panel>

        {/* 4. Unusual Usage: Unsafe Operation */}
        <Panel
          title="4. OPERATION PATTERNS"
          right={
            <span className={"num text-[10px] " + (noSignal ? "text-slate-500" : unsafeOperation ? "text-danger" : "text-good")}>
              {noSignal ? "NO SIGNAL" : unsafeOperation ? "HARSH PATTERN" : "CONTROLLED"}
            </span>
          }
          className={unsafeOperation ? "border-danger/70 shadow-[0_0_20px_rgba(239,68,68,0.15)]" : undefined}
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="hud-label">VIBRATION</div>
              <div className={"mt-1 num text-lg " + ((vibration ?? 0) > 0.8 ? "text-warn" : "text-slate-200")}>
                {noSignal ? "—" : `${vibration!.toFixed(2)} `}{noSignal ? "" : <span className="text-xs text-slate-500">g</span>}
              </div>
            </div>
            <div>
              <div className="hud-label">AGGRESSION</div>
              <div className={"mt-1 num text-lg " + ((aggression ?? 0) > 0.4 ? "text-warn" : "text-slate-200")}>
                {noSignal ? "—" : `${((aggression ?? 0) * 100).toFixed(0)}%`}
              </div>
            </div>
          </div>
          <div className="mt-3 text-xs leading-relaxed text-slate-400">
            {noSignal
              ? "Pattern analysis standing by for telemetry."
              : unsafeOperation
              ? "Aggressive machine handling detected! Rapid throttle bursts or excessive speed over rough terrain."
              : "Operator inputs and machine motion are smooth and within safe envelope."}
          </div>
        </Panel>
      </div>

      {/* Working Conditions Impact Box */}
      <Panel title="REAL-TIME WORKING CONDITIONS & ENVIRONMENTAL IMPACT" right={<span className="num text-[10px] text-holo">SITE TELEMETRY</span>}>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div className="rounded border border-carbon-700/60 bg-carbon-950/30 p-3">
            <div className="hud-label">WEATHER EVENT</div>
            <div className="mt-1 num text-base text-slate-100">{noSignal ? "—" : weather}</div>
            <div className="mt-1 text-[11px] text-slate-500">{noSignal ? "No telemetry" : (rainfall ?? 0) > 0 ? `${rainfall!.toFixed(1)} mm/h rain` : "No precipitation"}</div>
          </div>
          <div className="rounded border border-carbon-700/60 bg-carbon-950/30 p-3">
            <div className="hud-label">TERRAIN CONDITION</div>
            <div className={"mt-1 num text-base " + (noSignal ? "text-slate-500" : terrain === "MUDDY" || terrain === "ICY" ? "text-warn" : "text-slate-100")}>{noSignal ? "—" : terrain}</div>
            <div className="mt-1 text-[11px] text-slate-500">{noSignal ? "No telemetry" : terrain === "MUDDY" ? "Traction -25%" : "Stable traction"}</div>
          </div>
          <div className="rounded border border-carbon-700/60 bg-carbon-950/30 p-3">
            <div className="hud-label">VISIBILITY</div>
            <div className={"mt-1 num text-base " + (noSignal ? "text-slate-500" : (visibility ?? 9999) < 1000 ? "text-warn" : "text-slate-100")}>{noSignal ? "—" : `${visibility!.toFixed(0)} m`}</div>
            <div className="mt-1 text-[11px] text-slate-500">{noSignal ? "No telemetry" : (visibility ?? 9999) < 1500 ? "Use extra caution" : "Clear sightline"}</div>
          </div>
          <div className="rounded border border-carbon-700/60 bg-carbon-950/30 p-3">
            <div className="hud-label">GROUND SLOPE</div>
            <div className={"mt-1 num text-base " + (noSignal ? "text-slate-500" : (slope ?? 0) > 8 ? "text-warn" : "text-slate-100")}>{noSignal ? "—" : `${slope!.toFixed(1)}°`}</div>
            <div className="mt-1 text-[11px] text-slate-500">{noSignal ? "No telemetry" : (slope ?? 0) > 10 ? "Rollover risk" : "Safe working grade"}</div>
          </div>
          <div className="rounded border border-carbon-700/60 bg-carbon-950/30 p-3">
            <div className="hud-label">SAFETY FACTOR</div>
            <div className="mt-1 num text-base text-good">{noSignal ? "—" : (sit?.safety_state ?? "—")}</div>
            <div className="mt-1 text-[11px] text-slate-500">Risk: {noSignal ? "—" : (sit?.current_risk ?? "—")}</div>
          </div>
        </div>
      </Panel>

      {/* Approved Safety Procedures (SOPs) */}
      <div>
        <div className="hud-label mb-2 text-slate-400">APPROVED OPERATOR SAFETY PROCEDURES (SOP)</div>
        <div className="grid gap-4 md:grid-cols-2">
          {procedures.map((procedure) => (
            <Panel
              key={procedure.id}
              title={procedure.title}
              right={<span className={"num text-[10px] " + (procedure.severity === "CRITICAL" ? "text-danger" : "text-warn")}>{procedure.severity}</span>}
            >
              <ol className="flex flex-col gap-3">
                {procedure.steps.map((step, index) => (
                  <li key={step} className="flex gap-3 text-sm text-slate-300">
                    <span className="num text-holo">0{index + 1}</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </Panel>
          ))}
        </div>
      </div>
    </div>
  );
}
