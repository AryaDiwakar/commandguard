import type { TelemetryFrame } from "../lib/types";

const tempTone = (c?: number) => {
  if (c == null) return "#22d3ee";
  if (c >= 108) return "#ef4444";
  if (c >= 98) return "#f59e0b";
  return "#22d3ee";
};

const riskTone = (state?: string, proximity?: number, belt?: string) => {
  if (belt === "Unfastened") return "#ef4444";
  if (proximity != null && proximity < 4) return "#ef4444";
  if (proximity != null && proximity < 8) return "#f59e0b";
  if (state === "STOPPED" || state === "SHUTDOWN") return "#34d399";
  return "#22d3ee";
};

export function MachineHolo({ frame }: { frame: TelemetryFrame | null }) {
  const f = frame;
  const temp = f?.engine_temperature_c;
  const load = f?.engine_load_pct;
  const proximity = f?.proximity_distance_m;
  const belt = f?.Seatbelt_Status;
  const hullTone = riskTone(f?.machine_state, proximity, belt);
  const engineTone = tempTone(temp);

  const boomTipX = 300 + (load ?? 0) * 0.52;
  const boomTipY = 150 - (load ?? 0) * 0.52;

  return (
    <div className="relative overflow-hidden rounded-lg border border-carbon-700/80 bg-carbon-900/70">
      <div className="pointer-events-none absolute inset-x-0 -top-10 h-32 animate-sweep bg-gradient-to-b from-transparent via-holo/10 to-transparent" />
      <div className="hud-label absolute left-2 top-2 flex items-center gap-1.5">
        <span className="text-holo">◆</span> MACHINE ENVIRONMENT · {f?.Machine_ID ?? "—"}
        {f?.machine_state ? (
          <span className="text-[9px] text-slate-500">· {f.machine_state}</span>
        ) : null}
      </div>

      <svg viewBox="0 0 400 260" className="w-full">
        <defs>
          <linearGradient id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1e293b" />
            <stop offset="100%" stopColor="#0f172a" />
          </linearGradient>
        </defs>

        {/* ground */}
        <line x1="20" y1="212" x2="380" y2="212" stroke="#1e293b" strokeWidth="1" strokeDasharray="6 6" />

        {/* track */}
        <ellipse cx="210" cy="212" rx="120" ry="22" fill="none" stroke={hullTone} strokeOpacity="0.35" strokeWidth="4" />
        <line x1="90" y1="212" x2="330" y2="212" stroke={hullTone} strokeOpacity="0.7" strokeWidth="4" />

        {/* proximity radar */}
        {proximity != null ? (
          <g>
            <circle cx="210" cy="212" r="150" fill="none" stroke={proximity < 8 ? "#ef4444" : "#22d3ee"} strokeOpacity={proximity < 8 ? 0.55 : 0.08} strokeWidth={proximity < 8 ? 2 : 1} />
            <circle cx="210" cy="212" r="100" fill="none" stroke="#22d3ee" strokeOpacity="0.12" />
            <circle cx="210" cy="212" r="150" fill="none" stroke={hullTone} strokeOpacity="0.35" strokeWidth={proximity < 8 ? 1.5 : 0.75} strokeDasharray="4 8" />
            <text x="246" y="70" fontSize="8" fill={proximity < 8 ? "#ef4444" : "#22d3ee"} opacity="0.9">{proximity.toFixed(1)} m</text>
          </g>
        ) : (
          <g>
            <circle cx="210" cy="212" r="150" fill="none" stroke="#22d3ee" strokeOpacity="0.08" />
            <circle cx="210" cy="212" r="100" fill="none" stroke="#22d3ee" strokeOpacity="0.12" />
          </g>
        )}

        {/* body */}
        <path
          d="M120 150 Q210 96 300 150 L320 212 L100 212 Z"
          fill="url(#bodyGrad)"
          stroke={hullTone}
          strokeOpacity="0.8"
          strokeWidth="2"
        />
        {/* engine block (live thermal state) */}
        <rect x="250" y="112" width="46" height="34" rx="4" fill={engineTone} fillOpacity="0.12" stroke={engineTone} strokeOpacity="0.7" />
        <text x="273" y="133" textAnchor="middle" fontSize="9" fill={engineTone} opacity="0.9">★ ENG</text>
        {temp != null ? <text x="273" y="152" textAnchor="middle" fontSize="7" fill={engineTone} opacity="0.8">{temp.toFixed(0)}°C</text> : null}
        {/* cab */}
        <rect x="138" y="116" width="40" height="28" rx="3" fill="#22d3ee" fillOpacity="0.10" stroke="#22d3ee" strokeOpacity="0.6" />
        {belt === "Unfastened" ? <text x="158" y="134" textAnchor="middle" fontSize="7" fill="#ef4444">BELT</text> : null}
        {/* boom (live articulation) */}
        <line x1="300" y1="150" x2={boomTipX} y2={boomTipY} stroke="#f6a821" strokeOpacity="0.75" strokeWidth="5" />
        <line x1={boomTipX} y1={boomTipY} x2={boomTipX + 30} y2={boomTipY + 24} stroke="#f6a821" strokeOpacity="0.5" strokeWidth="4" />
        <path d={`M${boomTipX + 20} ${boomTipY + 24} L${boomTipX + 40} ${boomTipY + 36} L${boomTipX + 30} ${boomTipY + 56} L${boomTipX + 12} ${boomTipY + 44} Z`} fill="#f6a821" fillOpacity="0.18" stroke="#f6a821" strokeOpacity="0.7" />
        {/* fuel bar */}
        {f?.fuel_level_pct != null ? (
          <g>
            <rect x="120" y="222" width="160" height="6" rx="3" fill="#0f172a" stroke="#334155" strokeWidth="0.5" />
            <rect x="121" y="223" width={(f.fuel_level_pct / 100) * 158} height="4" rx="2" fill={f.fuel_level_pct <= 15 ? "#ef4444" : f.fuel_level_pct <= 35 ? "#f59e0b" : "#34d399"} />
            <text x="288" y="228" fontSize="7" fill="#94a3b8">{f.fuel_level_pct.toFixed(0)}%</text>
          </g>
        ) : null}
      </svg>

      <div className="absolute bottom-2 left-2 flex flex-wrap gap-2">
        <span className="rounded border border-carbon-600/70 bg-carbon-900/80 px-1.5 py-0.5 num text-[10px] text-slate-400">
          STATE <span className="text-holo">{f?.machine_state ?? "—"}</span>
        </span>
        <span className="rounded border border-carbon-600/70 bg-carbon-900/80 px-1.5 py-0.5 num text-[10px] text-slate-400">
          LOAD <span className="text-holo">{f?.engine_load_pct?.toFixed(0) ?? "—"}%</span>
        </span>
        <span className="rounded border border-carbon-600/70 bg-carbon-900/80 px-1.5 py-0.5 num text-[10px] text-slate-400">
          RPM <span className="text-holo">{f?.engine_rpm?.toFixed(0) ?? "—"}</span>
        </span>
        <span className="rounded border border-carbon-600/70 bg-carbon-900/80 px-1.5 py-0.5 num text-[10px] text-slate-400">
          ZONE <span className="text-signal">{f?.work_zone ?? "—"}</span>
        </span>
        <span className="rounded border border-carbon-600/70 bg-carbon-900/80 px-1.5 py-0.5 num text-[10px] text-slate-400">
          TERRAIN <span className="text-slate-200">{f?.terrain_condition ?? "—"}</span>
        </span>
      </div>
    </div>
  );
}