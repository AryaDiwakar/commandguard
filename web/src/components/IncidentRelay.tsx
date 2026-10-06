import type { Incident } from "../lib/types";
import { Panel } from "./Panel";

export function IncidentRelay({
  incident,
  onRequestHelp,
  onAcknowledge,
  onAction,
  onResume,
  onReport,
  onReplay,
}: {
  incident: Incident | null;
  onRequestHelp: () => void;
  onAcknowledge: () => void;
  onAction: (action: string) => void;
  onResume: () => void;
  onReport: () => void;
  onReplay: () => void;
}) {
  if (!incident) {
    return (
      <Panel
        title="LIVE HELP RELAY"
        right={<span className="num text-[10px] text-good">RELAY STANDBY</span>}
      >
        <div className="flex items-center gap-3 py-3 text-sm text-slate-500">
          <span className="h-2 w-2 rounded-full bg-good shadow-[0_0_12px_rgba(34,197,94,0.8)]" />
          No active incident. Machine context is continuously monitored.
        </div>
      </Panel>
    );
  }

  const requested = incident.help_status !== "NOT_REQUESTED";
  const resolved = incident.status === "RESOLVED";

  return (
    <Panel
      title="LIVE HELP RELAY"
      right={
        <span className={"num text-[10px] " + (resolved ? "text-good" : "text-danger")}>
          {resolved ? "INCIDENT RESOLVED" : `RISK · ${incident.severity}`}
        </span>
      }
      className={resolved ? "border-good/30" : "border-danger/50 shadow-[0_0_30px_rgba(239,68,68,0.08)]"}
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_1.6fr_0.9fr]">
        <div>
          <div className="hud-label text-danger">MACHINE INTELLIGENCE EVENT</div>
          <h2 className="mt-1 text-lg font-semibold tracking-wide text-slate-100">{incident.incident_type.replace(/_/g, " ")}</h2>
          <p className="mt-2 text-xs leading-relaxed text-slate-400">{incident.recommended_action}</p>
          <div className="mt-3 flex gap-4 text-xs">
            <span className="text-slate-500">CONF <b className="num text-slate-100">{incident.confidence.toFixed(2)}</b></span>
            <span className="text-slate-500">RELAY <b className={"num " + (requested ? "text-signal" : "text-slate-100")}>{incident.help_status.replace(/_/g, " ")}</b></span>
            <span className="text-slate-500">RESPONSE <b className={"num " + (incident.response_status === "VERIFIED" ? "text-good" : "text-slate-100")}>{incident.response_status.replace(/_/g, " ")}</b></span>
          </div>
        </div>

        <div className="border-l border-carbon-700/70 pl-4">
          <div className="hud-label">EVIDENCE STREAM</div>
          <div className="mt-2 flex flex-col gap-2">
            {incident.evidence.map((item) => (
              <div key={item.signal} className="rounded border border-carbon-700/70 bg-carbon-950/40 px-3 py-2">
                <div className="num text-[10px] text-holo">{item.signal}</div>
                <div className="mt-1 text-xs text-slate-200">{item.observation}</div>
                <div className="mt-0.5 text-[11px] text-slate-500">Expected: {item.expected}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col justify-end gap-2">
          {!requested && !resolved && (
            <button
              onClick={onRequestHelp}
              className="rounded border border-signal/70 bg-signal/10 px-3 py-2 num text-xs font-semibold tracking-widest text-signal transition hover:bg-signal/20"
            >
              REQUEST LIVE ASSISTANCE
            </button>
          )}
          {requested && incident.help_status === "REQUESTED" && !resolved && (
            <button
              onClick={onAcknowledge}
              className="rounded border border-holo/60 bg-holo/10 px-3 py-2 num text-xs font-semibold tracking-widest text-holo transition hover:bg-holo/20"
            >
              ACKNOWLEDGE SUPPORT
            </button>
          )}
          {!resolved && (
            <button
              onClick={() => onAction("STOP_MACHINE")}
              className="rounded border border-danger/60 bg-danger/10 px-3 py-2 num text-xs font-semibold tracking-widest text-danger transition hover:bg-danger/20"
            >
              STOP MACHINE SAFELY
            </button>
          )}
          {incident.auto_reaction && incident.response_status === "VERIFIED" && !resolved && (
            <button
              onClick={onResume}
              className="rounded border border-good/60 bg-good/10 px-3 py-2 num text-xs font-semibold tracking-widest text-good transition hover:bg-good/20"
            >
              RESUME WORK
            </button>
          )}
          <div className="mt-1 grid grid-cols-2 gap-2">
            <button
              onClick={onReport}
              className="rounded border border-carbon-600/80 bg-carbon-800/50 px-2 py-2 num text-[10px] tracking-widest text-slate-300 transition hover:border-holo/50 hover:text-holo"
            >
              INCIDENT REPORT
            </button>
            <button
              onClick={onReplay}
              className="rounded border border-carbon-600/80 bg-carbon-800/50 px-2 py-2 num text-[10px] tracking-widest text-slate-300 transition hover:border-holo/50 hover:text-holo"
            >
              REPLAY EVENT
            </button>
          </div>
          {requested && <div className="text-center text-[10px] leading-relaxed text-slate-500">Support receives the machine context, evidence, and live updates.</div>}
        </div>
      </div>
      <div className="mt-4 border-t border-carbon-700/70 pt-3">
        <div className="hud-label">INCIDENT TIMELINE</div>
        <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {incident.timeline.slice(-4).map((event) => (
            <div key={`${event.timestamp}-${event.type}`} className="rounded border border-carbon-700/60 bg-carbon-950/35 px-2 py-2">
              <div className="num text-[9px] text-holo">{event.type.replace(/_/g, " ")}</div>
              <div className="mt-1 text-[11px] leading-relaxed text-slate-400">{event.message}</div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
