import { useEffect, useState } from "react";

import { incidentPdfUrl, incidentReplay, incidentReport, listIncidents, maintenanceHandoff } from "../lib/api";
import type { Incident, IncidentReplay, IncidentReport, MaintenanceHandoff } from "../lib/types";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

export function IncidentCenterPage() {
  const { machineId } = useTelemetry();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [replay, setReplay] = useState<IncidentReplay | null>(null);
  const [handoff, setHandoff] = useState<MaintenanceHandoff | null>(null);

  useEffect(() => {
    listIncidents(machineId).then((result) => {
      setIncidents(result.incidents);
      setSelected(result.incidents[result.incidents.length - 1] ?? null);
    }).catch(() => undefined);
  }, [machineId]);

  const selectIncident = (incident: Incident) => {
    setSelected(incident);
    setReport(null);
    setReplay(null);
    setHandoff(null);
    incidentReport(incident.machine_id, incident.incident_id).then(setReport).catch(() => undefined);
    incidentReplay(incident.machine_id, incident.incident_id).then(setReplay).catch(() => undefined);
    maintenanceHandoff(incident.machine_id, incident.incident_id).then(setHandoff).catch(() => undefined);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      <header className="glass-panel flex items-end justify-between gap-4 px-5 py-5">
        <div><div className="hud-label text-holo">OPERATIONS / INCIDENT CENTER</div><h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-100">Incident intelligence archive</h1><p className="mt-2 max-w-2xl text-sm text-slate-500">Every alert becomes an auditable timeline: evidence, relay, operator response, verification, and learning.</p></div>
        <div className="num text-right text-xs text-slate-500"><div className="text-2xl text-slate-100">{incidents.length.toString().padStart(2, "0")}</div>RECORDED EVENTS</div>
      </header>
      <div className="grid gap-4 lg:grid-cols-[0.8fr_1.5fr]">
        <Panel title="EVENT STREAM" right={<span className="num text-[10px] text-holo">SESSION ARCHIVE</span>}>
          <div className="flex flex-col gap-2">
            {incidents.length === 0 && <div className="py-8 text-center text-sm text-slate-500">No incidents recorded for {machineId} yet. Start a scenario from Simulator.</div>}
            {incidents.map((incident) => (
              <button key={incident.incident_id} onClick={() => selectIncident(incident)} className={"rounded border px-3 py-3 text-left transition " + (selected?.incident_id === incident.incident_id ? "border-holo/60 bg-holo/10" : "border-carbon-700/70 bg-carbon-950/30 hover:border-carbon-500")}>
                <div className="flex items-center justify-between gap-2"><span className="num text-xs text-slate-200">{incident.incident_type.replace(/_/g, " ")}</span><span className={"num text-[10px] " + (incident.severity === "CRITICAL" || incident.severity === "HIGH" ? "text-danger" : "text-warn")}>{incident.severity}</span></div>
                <div className="mt-2 flex justify-between text-[10px] text-slate-500"><span>{incident.machine_id} · {incident.task_type}</span><span>{incident.response_status.replace(/_/g, " ")}</span></div>
              </button>
            ))}
          </div>
        </Panel>
        <div className="flex flex-col gap-4">
          {selected ? <>
            <Panel title="EVIDENCE & RESPONSE" right={<span className="num text-[10px] text-good">{selected.status}</span>}>
              <div className="grid gap-3 sm:grid-cols-3"><div><div className="hud-label">INCIDENT</div><div className="mt-1 num text-sm text-slate-100">{selected.incident_type.replace(/_/g, " ")}</div></div><div><div className="hud-label">CONFIDENCE</div><div className="mt-1 num text-sm text-holo">{selected.confidence.toFixed(2)}</div></div><div><div className="hud-label">RESPONSE</div><div className="mt-1 num text-sm text-good">{selected.response_status.replace(/_/g, " ")}</div></div></div>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">{selected.evidence.map((item) => <div key={item.signal} className="rounded border border-carbon-700/70 bg-carbon-950/40 px-3 py-2"><div className="num text-[10px] text-holo">{item.signal}</div><div className="mt-1 text-xs text-slate-200">{item.observation}</div><div className="mt-1 text-[11px] text-slate-500">{item.expected}</div></div>)}</div>
            </Panel>
            <div className="grid gap-4 md:grid-cols-2">
              {report && <Panel title="GENERATED REPORT"><div className="space-y-3 text-xs"><div><span className="hud-label">OUTCOME</span><p className="mt-1 text-good">{report.outcome.replace(/_/g, " ")}</p></div><div><span className="hud-label">FOLLOW-UP</span><p className="mt-1 text-slate-300">{report.recommended_follow_up}</p></div><div><span className="hud-label">TRAINING</span><p className="mt-1 text-holo">{report.training_recommendation}</p></div><a href={incidentPdfUrl(selected.machine_id, selected.incident_id)} download className="mt-3 inline-block rounded border border-signal/60 bg-signal/10 px-3 py-2 num text-[10px] tracking-widest text-signal">DOWNLOAD PDF</a></div></Panel>}
              {replay && <Panel title="REPLAY SIGNAL"><div className="num text-2xl text-signal">{replay.frames.length} <span className="text-xs text-slate-500">FRAMES</span></div><div className="mt-4 flex h-16 items-end gap-px">{replay.frames.map((frame, index) => <span key={`${frame.timestamp_ms}-${index}`} className="flex-1 rounded-t bg-gradient-to-t from-holo/20 to-signal/80" style={{ height: `${Math.max(8, Math.min(100, frame.engine_temperature_c))}%` }} />)}</div><div className="mt-2 flex justify-between hud-label"><span>START</span><span>RECOVERY</span></div></Panel>}
            </div>
            {handoff && <Panel title="MAINTENANCE HANDOFF PACKET" right={<span className="num text-[10px] text-signal">READY TO RELAY</span>}><div className="grid gap-3 sm:grid-cols-3"><div><div className="hud-label">OPERATOR</div><div className="mt-1 num text-sm text-slate-100">{handoff.operator_id}</div></div><div><div className="hud-label">TASK</div><div className="mt-1 num text-sm text-slate-100">{handoff.task}</div></div><div><div className="hud-label">REPLAY</div><div className="mt-1 num text-sm text-holo">{handoff.replay_frame_count} frames</div></div></div><p className="mt-3 text-xs text-slate-400">{handoff.recommended_follow_up}</p><p className="mt-2 text-[10px] text-slate-500">{handoff.safe_boundary}</p></Panel>}
          </> : <Panel title="INCIDENT DETAIL"><div className="py-16 text-center text-sm text-slate-500">Select an incident to inspect its evidence and replay.</div></Panel>}
        </div>
      </div>
    </div>
  );
}
