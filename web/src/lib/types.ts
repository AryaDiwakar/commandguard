export interface TelemetryFrame {
  Timestamp: string;
  timestamp_ms: number;
  Machine_ID: string;
  Operator_ID: string;
  Engine_Hours: number;
  Fuel_Used_L: number;
  Load_Cycles: number;
  Idling_Time_min: number;
  Seatbelt_Status: string;
  Safety_Alert_Triggered: boolean;
  fuel_level_pct: number;
  fuel_consumption_rate_lph: number;
  engine_rpm: number;
  engine_temperature_c: number;
  coolant_temperature_c: number;
  oil_pressure_kpa: number;
  hydraulic_pressure_bar: number;
  hydraulic_temperature_c: number;
  battery_voltage_v: number;
  engine_load_pct: number;
  machine_speed_kph: number;
  vibration_g: number;
  proximity_distance_m: number;
  operating_hours: number;
  latitude: number;
  longitude: number;
  ambient_temperature_c: number;
  humidity_pct: number;
  rainfall_mmh: number;
  visibility_m: number;
  terrain_type: string;
  terrain_condition: string;
  slope_deg: number;
  work_zone: string;
  nearby_machine_count: number;
  weather_event: string;
  machine_state: string;
  task_progress_pct: number;
  efficiency: number;
  aggression_index: number;
  compliance: number;
  cooling_performance_pct: number;
  diagnostics_consistency: number;
  scenario_type?: string;
  phase?: string;
  anomaly_label?: boolean;
  incident_type?: string | null;
  incident_severity?: string | null;
  session_id: string;
  current_task_type: string;
  task_id: string;
  task_index: number;
  task_count: number;
  task_status: string;
  task_planned_minutes: number;
  task_completed: boolean;
  completed_task_type?: string | null;
  completed_task_id?: string | null;
  next_task_type: string;
  next_task_id: string;
  shift_total_minutes: number;
  shift_remaining_minutes: number;
  refuel_event?: boolean;
}

export interface Evidence {
  signal: string;
  observation: string;
  expected: string;
  contribution: number;
}

export interface IncidentEvent {
  type: string;
  message: string;
  timestamp: string;
}

export interface Incident {
  incident_id: string;
  machine_id: string;
  operator_id: string;
  task_id: string;
  task_type: string;
  incident_type: string;
  severity: string;
  confidence: number;
  detected_at: string;
  status: string;
  response_status: string;
  last_operator_action: string | null;
  auto_reaction: string | null;
  auto_reaction_reason: string | null;
  evidence: Evidence[];
  possible_causes: string[];
  recommended_action: string;
  help_status: string;
  timeline: IncidentEvent[];
  resolved_at: string | null;
}

export interface IncidentReport {
  report_type: string;
  generated_at: string;
  incident: Incident;
  operator_actions: IncidentEvent[];
  outcome: string;
  recommended_follow_up: string;
  training_recommendation: string;
}

export interface IncidentReplay {
  incident_id: string;
  machine_id: string;
  start_timestamp_ms: number;
  end_timestamp_ms: number;
  frames: TelemetryFrame[];
  timeline: IncidentEvent[];
}

export interface MachineSituation {
  machine_id: string;
  timestamp_ms: number;
  operating_state: string;
  machine_health: string;
  safety_state: string;
  task: string;
  task_progress_pct: number;
  task_index: number;
  task_count: number;
  task_status: string;
  next_task_type: string;
  next_task_id: string;
  shift_total_minutes: number;
  shift_remaining_minutes: number;
  current_risk: string;
  active_incidents: unknown[];
  predicted_risks: PredictedRisk[];
  eta_minutes: number;
  eta_baseline_minutes: number;
  eta_reasons: string[];
  early_warnings: Array<{ signal: string; type: string; z_score: number; direction: string; message: string; confidence: number }>;
  component_health: Record<string, { score: number; trend: string }>;
  maintenance_forecasts: Array<{ component: string; health_score: number; forecast: string; time_to_maintenance_hours: number; reason: string }>;
  behavior_score: number;
  fatigue_risk: string;
  pre_shift_risk: string;
  pre_shift_risk_score: number;
  pre_shift_reasons: string[];
  productivity: { output_quantity: number; target_quantity: number; output_unit: string; rate_per_min: number; fuel_efficiency_output_per_l: number; recommended_practice: string; score: number };
  confidence: number;
  mode: string;
}

export interface PredictedRisk {
  type: string;
  severity: string;
  confidence: number;
  time_to_threshold_min: number;
  message: string;
}

export interface TaskSchedule {
  Task_ID: string;
  Task_Type: string;
  Weather: string;
  Estimated_Time_min: number;
  Actual_Time_min: number;
  Task_Zone: string;
  Task_Priority: string;
  Terrain_Condition: string;
  Machine_ID: string;
  Scheduled_Start_Time: string;
  Reference_Time_min?: number;
  Machine_Age_yrs?: number;
  Rainfall_mmh?: number;
  Visibility_m?: number;
  model_predicted_min?: number;
}

export interface TodayTasksResponse {
  machine_id: string;
  tasks: TaskSchedule[];
  data_mode: string;
  eta_model: { model_name: string; training_rows: number; holdout_mae_minutes: number; holdout_rmse_minutes: number };
}

export interface ScenarioOption {
  type: string;
  label: string;
  default_plan: Record<string, number | string>;
}

export interface TrainingModule {
  module_id: string;
  title: string;
  scenario: string;
  description: string;
  step_count: number;
}

export interface TrainingStep {
  id: string;
  title: string;
  prompt: string;
  options: string[];
}

export interface TrainingState {
  session_id: string;
  module_id: string;
  operator_id: string;
  title: string;
  scenario: string;
  step_index: number;
  step_count: number;
  step: TrainingStep | null;
  mistakes: number;
  score: number | null;
  complete: boolean;
  actions: Array<{ step_id: string; action: string; correct: boolean }>;
  feedback: string;
  correct?: boolean;
  last_action?: string;
}

export interface SafetyProcedure {
  id: string;
  title: string;
  severity: string;
  steps: string[];
}

export interface AnalyticsOverview {
  generated_at: string;
  data_mode: string;
  filters: { machine_id: string | null; operator_id: string | null };
  metrics: {
    total_incidents: number;
    active_incidents: number;
    resolved_incidents: number;
    high_critical_incidents: number;
    verified_responses: number;
    response_verification_rate: number;
    average_confidence: number;
  };
  by_type: Array<{ label: string; count: number }>;
  by_severity: Array<{ label: string; count: number }>;
  by_response: Array<{ label: string; count: number }>;
  daily_trend: Array<{ date: string; count: number }>;
  recent_incidents: Array<{
    incident_id: string;
    machine_id: string;
    operator_id: string;
    type: string;
    severity: string;
    status: string;
    response_status: string;
    confidence: number;
    detected_at: string | null;
  }>;
  current_situation: MachineSituation | null;
  task_metrics: {
    tasks: number;
    average_estimated_minutes: number;
    average_actual_minutes: number;
    average_efficiency: number;
    over_estimate_rate: number;
  };
  operator_performance: Array<{
    operator_id: string;
    tasks: number;
    average_efficiency: number;
    incidents: number;
    verified_response_rate: number;
  }>;
  eta_model: { model_name: string; training_rows: number; holdout_mae_minutes: number; holdout_rmse_minutes: number };
  history: { label: string; source: string; days: number; rows: number; generated_at: string };
}

export interface AssistantReply {
  message: string;
  grounded: boolean;
  sources: string[];
  suggested_actions: string[];
  knowledge?: Array<{ document_id: string; title: string; source: string; excerpt: string; score: number }>;
  context?: {
    machine_id: string;
    timestamp_ms: number;
    operating_state: string;
    machine_health: string;
    safety_state: string;
    current_risk: string;
    active_incidents: string[];
  };
}

export interface Principal {
  operator_id: string;
  role: string;
  display_name: string;
}

export interface DashboardData {
  machine_id: string;
  data_mode: string;
  live: boolean;
  frame: TelemetryFrame | null;
  situation: MachineSituation | null;
  active_incidents: Incident[];
  recent_incidents: Incident[];
  current_task: TaskSchedule | null;
  task_schedule: TaskSchedule[];
  pre_start: { readiness: string; focus: string[]; environment: Record<string, string | number | null> };
  shift_handoff: { open_incidents: Incident[]; recent_incidents: Incident[]; handoff_notes: string[]; machine_state: MachineSituation | null };
}

export interface WhatIfProjection {
  machine_id: string;
  action: string;
  grounded: boolean;
  current: { risk: string; eta_minutes: number; safety: string };
  projection: { risk: string; eta_minutes: number; message: string };
  assumptions: string[];
  evidence: PredictedRisk[];
}

export interface PracticeComparison {
  machine_id: string;
  task: string;
  grounded: boolean;
  recommendation: string;
  reason: string;
  comparisons: Array<{ profile: string; description: string; task_time_minutes: number; fuel_liters: number; output_quantity: number; output_unit: string; output_per_minute: number; fuel_efficiency_output_per_l: number; wear_multiplier: number; risk: string; score: number }>;
}

export interface MaintenanceHandoff {
  packet_type: string;
  incident: Incident;
  machine_id: string;
  operator_id: string;
  task: string;
  severity: string;
  evidence: Evidence[];
  operator_actions: IncidentEvent[];
  outcome: string;
  recommended_follow_up: string;
  replay_frame_count: number;
  safe_boundary: string;
}

export interface WsMessage {
  type: string;
  machine_id: string;
  frame?: TelemetryFrame;
  situation?: MachineSituation;
  events?: unknown[];
  incident?: Incident;
}

export interface SystemStatus {
  name: string;
  data_mode: string;
  running: boolean;
  disclaimer: string;
  version: string;
}
