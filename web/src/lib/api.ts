export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const BASE = API_BASE;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface ScenarioLaunchOpts {
  type: string;
  severity?: number;
  onset_offset_s?: number;
  ramp_s?: number;
}

export const startSession = (opts: { machine_id?: string; speed?: number; seed?: number; scenario?: ScenarioLaunchOpts } = {}) =>
  api<{ machine_id: string; running: boolean; speed: number }>("/api/simulation/start", {
    method: "POST",
    body: JSON.stringify(opts),
  });

export const stopSession = (machineId: string) =>
  api<{ stopped: string }>("/api/simulation/stop", {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId }),
  });

export const updateSpeed = (machineId: string, speed: number) =>
  api<{ machine_id: string; running: boolean; speed: number }>(`/api/simulation/${encodeURIComponent(machineId)}/speed`, {
    method: "PATCH",
    body: JSON.stringify({ speed }),
  });

export const machineState = (machineId: string) => api<{ frame: never; situation: never }>(`/api/state/${encodeURIComponent(machineId)}`);

export const liveSituation = (machineId: string) =>
  api<{ frame: import("./types").TelemetryFrame | null; situation: import("./types").MachineSituation | null }>(`/api/state/${encodeURIComponent(machineId)}`);

export const systemStatus = () => api<import("./types").SystemStatus>("/api/system/status");

export const requestHelp = (machineId: string, incidentId?: string) =>
  api<{ machine_id: string; relay: import("./types").Incident }>(`/api/incidents/${machineId}/help`, {
    method: "POST",
    body: JSON.stringify({ incident_id: incidentId, channel: "SUPERVISOR" }),
  });

export const acknowledgeHelp = (machineId: string, incidentId?: string) =>
  api<{ machine_id: string; relay: import("./types").Incident }>(`/api/incidents/${machineId}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ incident_id: incidentId }),
  });

export const sendOperatorAction = (machineId: string, action: string, incidentId?: string) =>
  api<{ machine_id: string; action: string; incident: import("./types").Incident }>(`/api/incidents/${machineId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, incident_id: incidentId }),
  });

export const incidentReport = (machineId: string, incidentId: string) =>
  api<import("./types").IncidentReport>(`/api/incidents/${machineId}/${incidentId}/report`);

export const incidentReplay = (machineId: string, incidentId: string) =>
  api<import("./types").IncidentReplay>(`/api/incidents/${machineId}/${incidentId}/replay`);

export const scenarioCatalog = () =>
  api<{ scenarios: import("./types").ScenarioOption[] }>("/api/simulation/scenarios");

export const injectScenario = (machineId: string, type: string, opts: Partial<ScenarioLaunchOpts> = {}) =>
  api<{ machine_id: string; injected: boolean; scenario_type: string; onset_s: number; resolve_s: number }>(`/api/simulation/scenario`, {
    method: "POST",
    body: JSON.stringify({
      machine_id: machineId,
      scenario: {
        type,
        severity: opts.severity ?? 0.85,
        onset_offset_s: opts.onset_offset_s ?? 30,
        ramp_s: opts.ramp_s ?? 8,
      },
    }),
  });

export const simulationStatus = () =>
  api<{ data_mode: string; sessions: Record<string, { machine_id: string; speed: number; running: boolean }> }>("/api/simulation/status");

export const todayTasks = (machineId: string) =>
  api<import("./types").TodayTasksResponse>(`/api/tasks/today?machine_id=${encodeURIComponent(machineId)}`);

export const listIncidents = (machineId: string) =>
  api<{ machine_id: string; incidents: import("./types").Incident[] }>(`/api/incidents/${encodeURIComponent(machineId)}`);

export const safetyProcedures = () =>
  api<{ procedures: import("./types").SafetyProcedure[] }>("/api/safety/procedures");

export const trainingModules = () =>
  api<{ modules: import("./types").TrainingModule[] }>("/api/training/modules");

export const trainingRecommendations = (operatorId: string) =>
  api<{ operator_id: string; recommendations: Array<{ module_id: string; title: string; reason: string }> }>(`/api/training/recommendations/${encodeURIComponent(operatorId)}`);

export const startTraining = (moduleId: string, operatorId: string) =>
  api<import("./types").TrainingState>("/api/training/sessions", {
    method: "POST",
    body: JSON.stringify({ module_id: moduleId, operator_id: operatorId }),
  });

export const trainingAction = (sessionId: string, action: string) =>
  api<import("./types").TrainingState>(`/api/training/sessions/${encodeURIComponent(sessionId)}/actions`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });

export const analyticsOverview = (machineId?: string, operatorId?: string) => {
  const params = new URLSearchParams();
  if (machineId) params.set("machine_id", machineId);
  if (operatorId) params.set("operator_id", operatorId);
  return api<import("./types").AnalyticsOverview>(`/api/analytics/overview?${params.toString()}`);
};

export const askAssistant = (machineId: string, message: string) =>
  api<import("./types").AssistantReply>("/api/assistant/message", {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId, message }),
  });

export const authMe = () =>
  api<{ authenticated: boolean; principal: import("./types").Principal }>("/api/auth/me");

export const dashboardData = (machineId: string) =>
  api<import("./types").DashboardData>(`/api/dashboard/${encodeURIComponent(machineId)}`);

export const whatIf = (machineId: string, action: "CONTINUE" | "STOP" | "REDUCE_LOAD") =>
  api<import("./types").WhatIfProjection>("/api/what-if/project", {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId, action }),
  });

export const resetDemo = () =>
  api<{ reset: boolean; message: string }>("/api/demo/reset", { method: "POST" });

export const bootFleet = () =>
  api<{ booted: boolean; machines: boolean[] }>("/api/demo/boot", { method: "POST" });

export const maintenanceHandoff = (machineId: string, incidentId: string) =>
  api<import("./types").MaintenanceHandoff>(`/api/incidents/${encodeURIComponent(machineId)}/${encodeURIComponent(incidentId)}/handoff`);

export const operatorInput = (machineId: string, action: "FASTEN_SEATBELT" | "UNFASTEN_SEATBELT" | "TOGGLE_SEATBELT" | "STOP_MACHINE" | "REDUCE_LOAD" | "RESUME") =>
  api<{ machine_id: string; action: string; seatbelt_status: string; message: string }>("/api/operator/input", {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId, action }),
  });

export const fleetOverview = () =>
  api<{ data_mode: string; machines: Array<{ machine_id: string; model: string; site: string; live: boolean; operator_id: string; machine_health: string; current_risk: string; pre_shift_risk: string; behavior_score: number | null; fatigue_risk: string; task: string | null; eta_minutes: number | null; active_incidents: import("./types").Incident[]; component_health: Record<string, { score: number; trend: string }> }> }>("/api/fleet/overview");

export const practiceCompare = (machineId: string) =>
  api<import("./types").PracticeComparison>("/api/practice/compare", {
    method: "POST",
    body: JSON.stringify({ machine_id: machineId }),
  });
    
export const wsUrl = (machineId: string) => {
  const base = import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000";
  return `${base}/ws/telemetry?machine_id=${encodeURIComponent(machineId)}`;
};

export const incidentPdfUrl = (machineId: string, incidentId: string) =>
  `${API_BASE}/api/incidents/${encodeURIComponent(machineId)}/${encodeURIComponent(incidentId)}/pdf`;
