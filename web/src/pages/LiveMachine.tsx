import { useEffect, useRef, useState } from "react";
import { acknowledgeHelp, incidentReplay, incidentReport, liveSituation, operatorInput, requestHelp, sendOperatorAction, systemStatus, startSession, stopSession, todayTasks, updateSpeed } from "../lib/api";
import type { Incident, IncidentReplay as IncidentReplayData, IncidentReport as IncidentReportData, MachineSituation, SystemStatus, TaskSchedule } from "../lib/types";
import { TelemetrySocket } from "../lib/ws";
import { useTelemetry } from "../store/useTelemetry";
import { MACHINE_IDS } from "../lib/config";
import { playAlertTone } from "../lib/alertSound";
import { LiveIndicator } from "../components/LiveIndicator";
import { MachineHolo } from "../components/MachineHolo";
import { Panel } from "../components/Panel";
import { Readout } from "../components/Readout";
import { TeleChart } from "../components/TeleChart";
import { VitalsRail } from "../components/VitalsRail";
import { IncidentRelay } from "../components/IncidentRelay";
import { IncidentArtifacts } from "../components/IncidentArtifacts";
import { OperationalContext } from "../components/OperationalContext";
import { incidentMatchesScenario } from "../lib/scenario";

const healthTone = (h: string) => (h === "HEALTHY" ? "good" : h === "WARNING" ? "warn" : "danger");
const safetyTone = (s: string) => (s === "SAFE" ? "good" : s === "UNSAFE" ? "danger" : "warn");
const riskTone = (r: string) => (r === "LOW" ? "good" : r === "MEDIUM" ? "warn" : "danger");

export function LiveMachinePage() {
  const { machineId, connected, latest, situation, incident, scenarioType, seatbeltStatus, frames, setMachine, setConnected, setSituation, setIncident, setSeatbeltStatus, pushFrames } =
    useTelemetry();
  const [sys, setSys] = useState<SystemStatus | null>(null);
  const [running, setRunning] = useState(true);
  const [speed, setSpeed] = useState(1);
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const [report, setReport] = useState<IncidentReportData | null>(null);
  const [replay, setReplay] = useState<IncidentReplayData | null>(null);
  const [tasks, setTasks] = useState<TaskSchedule[]>([]);
  const socketRef = useRef<TelemetrySocket | null>(null);

  useEffect(() => {
    systemStatus().then(setSys).catch(() => undefined);
  }, []);

  useEffect(() => {
    todayTasks(machineId).then((response) => setTasks(response.tasks)).catch(() => undefined);
  }, [machineId]);

  // Keep the command surface live even if a browser or proxy drops a WebSocket
  // event. The same frame also keeps the fuel trace visible during staging.
  useEffect(() => {
    if (!running) return undefined;
    const timer = window.setInterval(() => {
      liveSituation(machineId)
        .then((state) => {
          if (state.frame) pushFrames([state.frame]);
          if (state.situation) {
            setSituation(state.situation);
            const active = ((state.situation.active_incidents ?? []) as Incident[]).filter((item) => !scenarioType || incidentMatchesScenario(item.incident_type, scenarioType));
            setIncident(active[0] ?? null);
          }
        })
        .catch(() => undefined);
    }, 500);
    return () => window.clearInterval(timer);
  }, [machineId, running, pushFrames, scenarioType, setSituation, setIncident]);

  useEffect(() => {
    if (!running) return;

    startSession({ machine_id: machineId, speed: speedRef.current })
      .then(() => {
        setConnected(true);
      })
      .catch(() => undefined);

    const sock = new TelemetrySocket(machineId, pushFrames);
    sock.connect(setConnected, (msg) => {
      if (msg.situation) {
        setSituation(msg.situation);
          const active = (msg.situation.active_incidents as Incident[]).filter((item) => !scenarioType || incidentMatchesScenario(item.incident_type, scenarioType));
          setIncident(active[0] ?? null);
      }
      for (const event of msg.events ?? []) {
        if (typeof event === "object" && event !== null && "incident" in event) {
          const incidentEvent = event as { incident?: Incident };
          if (incidentEvent.incident && (!scenarioType || incidentMatchesScenario(incidentEvent.incident.incident_type, scenarioType))) setIncident(incidentEvent.incident);
        }
      }
      if (msg.incident && (!scenarioType || incidentMatchesScenario(msg.incident.incident_type, scenarioType))) setIncident(msg.incident);
    });
    socketRef.current = sock;
    return () => {
      sock.close();
    };
  }, [machineId, running, scenarioType, pushFrames, setConnected, setSituation, setIncident]);

  const changeSpeed = (next: number) => {
    setSpeed(next);
    speedRef.current = next;
    if (running) updateSpeed(machineId, next).catch(() => undefined);
  };

  const relayUpdate = (updated: Incident) => setIncident(updated);

  const toggle = async () => {
    if (running) {
      await stopSession(machineId).catch(() => undefined);
      socketRef.current?.close();
      setRunning(false);
    } else {
      setRunning(true);
    }
  };

  const f = latest;
  const sit: MachineSituation | null = situation;
  const toggleSeatbelt = () => {
    setSeatbeltStatus(seatbeltStatus === "Fastened" ? "Unfastened" : "Fastened");
    operatorInput(machineId, "TOGGLE_SEATBELT").catch(() => undefined);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      {/* ---------- command bar ---------- */}
      <header className="glass-panel flex flex-wrap items-center gap-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-bold tracking-[0.25em] text-cat">CAT</span>
          <span className="hud-label hidden sm:block">COMMANDGUARD / LIVE MACHINE</span>
          <span className="rounded border border-holo/40 bg-holo/10 px-2 py-0.5 num text-[10px] text-holo">
            {sys?.data_mode ?? "…"} MODE
          </span>
        </div>
        <div className="flex items-center gap-2">
          <LiveIndicator live={connected && running} />
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="hud-label">MACHINE</span>
            <select
              value={machineId}
              onChange={(e) => setMachine(e.target.value)}
              className="rounded border border-carbon-600/70 bg-carbon-800 px-2 py-1 num text-xs text-slate-200 outline-none focus:border-holo"
            >
              {MACHINE_IDS.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="hud-label">RATE</span>
            <select
              value={speed}
              onChange={(e) => changeSpeed(Number(e.target.value))}
              className="rounded border border-carbon-600/70 bg-carbon-800 px-2 py-1 num text-xs text-slate-200 outline-none focus:border-holo"
            >
              {[1, 2, 5, 10, 30].map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={toggle}
            className={
              "rounded border px-3 py-1 num text-xs font-semibold tracking-widest transition " +
              (running
                ? "border-danger/60 bg-danger/10 text-danger hover:bg-danger/20"
                : "border-good/60 bg-good/10 text-good hover:bg-good/20")
            }
          >
            {running ? "■ STOP" : "▶ START"}
          </button>
          <button onClick={toggleSeatbelt} className={"rounded border px-3 py-1 num text-xs font-semibold tracking-widest transition " + (seatbeltStatus === "Fastened" ? "border-good/50 bg-good/5 text-good" : "border-danger/60 bg-danger/10 text-danger")}>S · BELT {seatbeltStatus === "Fastened" ? "ON" : "OFF"}</button>
        </div>
      </header>

      <section className={"glass-panel flex flex-wrap items-center justify-between gap-3 border-l-4 px-4 py-3 " + (incident ? "border-l-danger" : sit?.safety_state === "SAFE" ? "border-l-good" : "border-l-warn")}>
        <div><div className="hud-label">RIGHT NOW</div><div className="mt-1 text-sm font-medium text-slate-100">{incident ? "Something needs your attention." : sit?.safety_state === "SAFE" ? "The machine is okay to monitor." : "Pause and check the safety guidance."}</div><div className="mt-1 text-xs text-slate-500">{incident ? incident.recommended_action : `Working on ${sit?.task ?? "the current task"}. CommandGuard is watching the live signals.`}</div></div>
        <div className={"rounded-full border px-3 py-1 num text-[10px] tracking-widest " + (incident ? "border-danger/50 bg-danger/10 text-danger" : "border-good/40 bg-good/5 text-good")}>{incident ? "ACTION NEEDED" : "MONITORING"}</div>
      </section>

      {!incident && sit?.predicted_risks.length ? (
        <section className="glass-panel flex flex-wrap items-center justify-between gap-3 border border-warn/50 bg-warn/5 px-4 py-3">
          <div>
            <div className="hud-label text-warn">EARLY WARNING · {sit.predicted_risks[0].type.replace(/_/g, " ")}</div>
            <div className="mt-1 text-sm text-slate-200">{sit.predicted_risks[0].message}</div>
            <div className="mt-1 text-xs text-slate-500">Formal live assistance opens when the detector confirms the incident. You can stop safely now.</div>
          </div>
          <button onClick={() => operatorInput(machineId, "STOP_MACHINE").catch(() => undefined)} className="rounded border border-danger/60 bg-danger/10 px-3 py-2 num text-xs font-semibold tracking-widest text-danger">STOP MACHINE SAFELY</button>
        </section>
      ) : null}


      <IncidentRelay
        incident={incident}
        onRequestHelp={() => {
          if (incident) requestHelp(machineId, incident.incident_id).then((res) => { relayUpdate(res.relay); playAlertTone("help"); }).catch(() => undefined);
        }}
        onAcknowledge={() => {
          if (incident) acknowledgeHelp(machineId, incident.incident_id).then((res) => { relayUpdate(res.relay); playAlertTone("help"); }).catch(() => undefined);
        }}
        onAction={(action) => {
          if (incident) sendOperatorAction(machineId, action, incident.incident_id).then((res) => { relayUpdate(res.incident); playAlertTone("confirm"); }).catch(() => undefined);
        }}
        onResume={() => {
          operatorInput(machineId, "RESUME").then(() => { setIncident(null); playAlertTone("verified"); }).catch(() => undefined);
        }}
        onReport={() => {
          if (incident) incidentReport(machineId, incident.incident_id).then(setReport).catch(() => undefined);
        }}
        onReplay={() => {
          if (incident) incidentReplay(machineId, incident.incident_id).then(setReplay).catch(() => undefined);
        }}
      />
      <IncidentArtifacts report={report} replay={replay} />
      <OperationalContext
        situation={sit}
        tasks={tasks}
        machineId={machineId}
      />

      {/* ---------- situation hero + machine ---------- */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="MACHINE SITUATION" className="lg:col-span-1">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-100">
                {sit?.operating_state ?? "—"}
              </span>
              <span className={"num text-xs " + (sit ? `text-${riskTone(sit.current_risk)}` : "text-slate-500")}>
                RISK · {sit?.current_risk ?? "—"}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Readout label="Health" value={sit?.machine_health ?? "—"} tone={healthTone(sit?.machine_health ?? "")} />
              <Readout label="Safety" value={sit?.safety_state ?? "—"} tone={safetyTone(sit?.safety_state ?? "")} />
              <Readout label="Task" value={sit?.task ?? "—"} tone="holo" />
            </div>
            <div>
              <div className="mb-1 flex justify-between">
                <span className="hud-label">TASK PROGRESS</span>
                <span className="num text-xs text-slate-300">{sit ? `${sit.task_progress_pct.toFixed(1)}%` : "—"}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-carbon-700">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-holo-dark to-holo transition-all"
                  style={{ width: `${sit?.task_progress_pct ?? 0}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
              <span>CONF</span>
              <span className="num text-slate-200">{(sit?.confidence ?? 0).toFixed(2)}</span>
              <span>MODE</span>
              <span className="num text-slate-200">{sit?.mode ?? "—"}</span>
            </div>
          </div>
        </Panel>

        <div className="lg:col-span-2">
          <MachineHolo frame={f} />
        </div>
      </div>

      {/* ---------- vitals rail ---------- */}
      <Panel title="VITALS RAIL · LIVE TRACE" right={<span className="num text-[10px] text-slate-500">{frames.length} samples</span>}>
        <VitalsRail frames={frames} />
      </Panel>

      {/* ---------- charts ---------- */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TeleChart
          title="FUEL LEVEL · %"
          frames={frames}
          series={[{ key: "fuel_level_pct", color: "#22c55e", domain: [0, 100], fitToData: true }]}
        />
        <TeleChart
          title="ENGINE RPM · min⁻¹"
          frames={frames}
          series={[{ key: "engine_rpm", color: "#22d3ee", domain: [0, 2300] }]}
        />
        <TeleChart
          title="ENGINE TEMP · °C"
          frames={frames}
          series={[{ key: "engine_temperature_c", color: "#f6a821", domain: [20, 120] }]}
        />
        <TeleChart
          title="HYDRAULIC PRESSURE · bar"
          frames={frames}
          series={[{ key: "hydraulic_pressure_bar", color: "#a78bfa", domain: [0, 260] }]}
        />
        <TeleChart
          title="ENGINE LOAD · %"
          frames={frames}
          series={[{ key: "engine_load_pct", color: "#f472b6", domain: [0, 100] }]}
        />
        <TeleChart
          title="SPEED + VIBRATION"
          frames={frames}
          series={[
            { key: "machine_speed_kph", color: "#34d399", domain: [0, 20] },
            { key: "vibration_g", color: "#f59e0b", domain: [0, 2] },
          ]}
        />
      </div>

      {/* ---------- readout panel ---------- */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="POWERTRAIN & FUEL">
          <div className="grid grid-cols-3 gap-3">
            <Readout label="Fuel" value={f?.fuel_level_pct.toFixed(1) ?? "—"} unit="%" tone="good" />
            <Readout label="Burn rate" value={f?.fuel_consumption_rate_lph.toFixed(1) ?? "—"} unit="L/h" tone="cat" />
            <Readout label="Fuel used" value={f?.Fuel_Used_L.toFixed(1) ?? "—"} unit="L" />
            <Readout label="Engine hrs" value={f?.Engine_Hours.toFixed(1) ?? "—"} unit="h" />
            <Readout label="Load cycles" value={f?.Load_Cycles ?? "—"} />
            <Readout label="Idle" value={f?.Idling_Time_min.toFixed(1) ?? "—"} unit="min" tone="warn" />
          </div>
        </Panel>

        <Panel title="FLUIDS & ELECTRICAL">
          <div className="grid grid-cols-3 gap-3">
            <Readout label="Coolant" value={f?.coolant_temperature_c.toFixed(1) ?? "—"} unit="°C" />
            <Readout label="Oil press" value={f?.oil_pressure_kpa.toFixed(0) ?? "—"} unit="kPa" />
            <Readout label="Hyd temp" value={f?.hydraulic_temperature_c.toFixed(1) ?? "—"} unit="°C" />
            <Readout label="Battery" value={f?.battery_voltage_v.toFixed(1) ?? "—"} unit="V" />
            <Readout label="Vibration" value={f?.vibration_g.toFixed(3) ?? "—"} unit="g" tone="warn" />
            <Readout label="Cooling" value={f?.cooling_performance_pct.toFixed(0) ?? "—"} unit="%" tone="holo" />
          </div>
        </Panel>

        <Panel title="ENVIRONMENT & SAFETY">
          <div className="grid grid-cols-3 gap-3">
            <Readout label="Ambient" value={f?.ambient_temperature_c.toFixed(1) ?? "—"} unit="°C" />
            <Readout label="Humidity" value={f?.humidity_pct.toFixed(0) ?? "—"} unit="%" />
            <Readout label="Rain" value={f?.rainfall_mmh.toFixed(1) ?? "—"} unit="mm/h" />
            <Readout label="Visib." value={f?.visibility_m.toFixed(0) ?? "—"} unit="m" />
            <Readout label="Slope" value={f?.slope_deg.toFixed(1) ?? "—"} unit="°" />
            <Readout label="Proximity" value={f?.proximity_distance_m.toFixed(0) ?? "—"} unit="m" />
            <Readout label="Seatbelt" value={f?.Seatbelt_Status ?? "—"} tone={f?.Seatbelt_Status === "Fastened" ? "good" : "danger"} />
            <Readout label="Machines" value={f?.nearby_machine_count ?? "—"} />
            <Readout label="Triggered" value={f?.Safety_Alert_Triggered ? "YES" : "NO"} tone={f?.Safety_Alert_Triggered ? "danger" : undefined} />
          </div>
        </Panel>
      </div>

      <footer className="hud-label pb-2 text-center text-slate-600">
        {sys?.disclaimer}
      </footer>
    </div>
  );
}
