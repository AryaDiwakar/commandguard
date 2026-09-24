import { injectScenario, simulationStatus, startSession } from "./api";
import type { ScenarioLaunchOpts } from "./api";

export interface ScenarioPlan {
  machineId: string;
  kind: "start" | "inject";
  speed: number;
  waitSec: number;
  type: string;
  severity: number;
  onsetS: number;
}

export const DEFAULT_SEVERITY = 0.85;
export const DEFAULT_ONSET_S = 30;

/**
 * Unified scenario entry point. If no session is running, it starts a fresh
 * one at 5× speed with the defect baked into the plan. If a session is already
 * running, it injects the defect into the live stream at the session's
 * current speed so telemetry is never interrupted.
 */
export async function launchScenario(
  machineId: string,
  type: string,
  opts: Partial<ScenarioLaunchOpts> = {}
): Promise<ScenarioPlan> {
  const severity = opts.severity ?? DEFAULT_SEVERITY;
  const onsetS = opts.onset_offset_s ?? DEFAULT_ONSET_S;

  try {
    await startSession({ machine_id: machineId, speed: 5, scenario: { type, severity, onset_offset_s: onsetS } });
    return { machineId, kind: "start", speed: 5, waitSec: Math.max(1, Math.round(onsetS / 5)), type, severity, onsetS };
  } catch {
    await injectScenario(machineId, type, { severity, onset_offset_s: onsetS, ramp_s: opts.ramp_s });
    let speed = 1;
    try {
      const status = await simulationStatus();
      speed = status.sessions[machineId]?.speed ?? 1;
    } catch {
      /* keep default */
    }
    return { machineId, kind: "inject", speed, waitSec: Math.max(1, Math.round(onsetS / speed)), type, severity, onsetS };
  }
}

export type ScenarioPhase =
  | "armed"
  | "staged"
  | "monitoring"
  | "detected"
  | "override"
  | "secured";

export function phaseLabel(phase: ScenarioPhase): { label: string; tone: string } {
  switch (phase) {
    case "armed":
      return { label: "ARMED", tone: "holo" };
    case "staged":
      return { label: "STAGED", tone: "warn" };
    case "monitoring":
      return { label: "MONITORING", tone: "warn" };
    case "detected":
      return { label: "DETECTED", tone: "warn" };
    case "override":
      return { label: "AUTO SAFETY OVERRIDE", tone: "danger" };
    case "secured":
      return { label: "SECURED", tone: "good" };
  }
}

export function phaseFromIncident(incident: { auto_reaction?: string | null; response_status?: string } | null): ScenarioPhase {
  if (!incident) return "monitoring";
  if (incident.response_status === "VERIFIED") return "secured";
  if (incident.auto_reaction) return "override";
  return "detected";
}

export function incidentMatchesScenario(incidentType: string, scenarioType: string): boolean {
  const aliases: Record<string, string> = {
    FUEL_LEAK: "FUEL_LEAK",
    ENGINE_OVERHEAT: "ENGINE_OVERHEAT",
    HYDRAULIC_FAILURE: "HYDRAULIC_FAILURE",
    PROXIMITY_HAZARD: "PROXIMITY_HAZARD",
    SEATBELT_VIOLATION: "SEATBELT",
    EXCESSIVE_IDLE: "EXCESSIVE_IDLE",
    UNSAFE_OPERATION: "UNSAFE_OPERATION",
    SENSOR_FAILURE: "SENSOR",
    BATTERY_ANOMALY: "BATTERY",
    MULTI_FACTOR_INCIDENT: "MULTI_FACTOR",
  };
  return incidentType.includes(aliases[scenarioType] ?? scenarioType);
}
