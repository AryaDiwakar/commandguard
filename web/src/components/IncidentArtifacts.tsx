import type { IncidentReplay, IncidentReport } from "../lib/types";
import { Panel } from "./Panel";

export function IncidentArtifacts({
  report,
  replay,
}: {
  report: IncidentReport | null;
  replay: IncidentReplay | null;
}) {
  if (!report && !replay) return null;

  const replayFrames = replay?.frames ?? [];
  const first = replayFrames[0];
  const last = replayFrames[replayFrames.length - 1];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {report && (
        <Panel title="AUTOMATED INCIDENT REPORT" right={<span className="num text-[10px] text-good">GENERATED</span>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <div className="hud-label">OUTCOME</div>
              <div className="mt-1 num text-sm text-good">{report.outcome.replace(/_/g, " ")}</div>
            </div>
            <div>
              <div className="hud-label">INCIDENT</div>
              <div className="mt-1 num text-sm text-slate-100">{report.incident.incident_type.replace(/_/g, " ")}</div>
            </div>
            <div className="sm:col-span-2 border-t border-carbon-700/70 pt-3">
              <div className="hud-label">FOLLOW-UP</div>
              <p className="mt-1 text-xs leading-relaxed text-slate-300">{report.recommended_follow_up}</p>
              <div className="mt-3 hud-label">TRAINING RECOMMENDATION</div>
              <p className="mt-1 text-xs leading-relaxed text-holo">{report.training_recommendation}</p>
            </div>
          </div>
        </Panel>
      )}

      {replay && (
        <Panel title="INCIDENT REPLAY" right={<span className="num text-[10px] text-holo">{replayFrames.length} FRAMES</span>}>
          <div className="grid grid-cols-3 gap-3">
            <div><div className="hud-label">START FUEL</div><div className="mt-1 num text-lg text-slate-100">{first?.fuel_level_pct.toFixed(1) ?? "—"}%</div></div>
            <div><div className="hud-label">END FUEL</div><div className="mt-1 num text-lg text-cat">{last?.fuel_level_pct.toFixed(1) ?? "—"}%</div></div>
            <div><div className="hud-label">END RPM</div><div className="mt-1 num text-lg text-good">{last?.engine_rpm.toFixed(0) ?? "—"}</div></div>
          </div>
          <div className="mt-4 flex h-12 items-end gap-px overflow-hidden rounded border border-carbon-700/60 bg-carbon-950/50 px-2 py-1">
            {replayFrames.map((frame, index) => {
              const height = Math.max(8, Math.min(100, frame.engine_temperature_c));
              return <span key={`${frame.timestamp_ms}-${index}`} className="flex-1 rounded-t bg-gradient-to-t from-cat/30 to-danger/80" style={{ height: `${height}%` }} />;
            })}
          </div>
          <div className="mt-2 flex justify-between hud-label"><span>TELEMETRY REPLAY</span><span>EVENT TRACE</span></div>
        </Panel>
      )}
    </div>
  );
}
