import type { ReactNode } from "react";

export function Readout({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: "good" | "warn" | "danger" | "holo" | "cat";
}) {
  const toneText: Record<string, string> = {
    good: "text-good",
    warn: "text-warn",
    danger: "text-danger",
    holo: "text-holo",
    cat: "text-cat",
  };
  return (
    <div className="flex flex-col gap-0.5">
      <span className="hud-label">{label}</span>
      <span className="flex items-baseline gap-1">
        <span className={"num text-lg font-semibold leading-none " + (toneText[tone ?? ""] ?? "text-slate-100")}>
          {value}
        </span>
        {unit && <span className="num text-[10px] text-slate-500">{unit}</span>}
      </span>
    </div>
  );
}