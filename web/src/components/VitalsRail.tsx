import { useEffect, useRef } from "react";
import type { TelemetryFrame } from "../lib/types";

const LANES: { key: keyof TelemetryFrame; label: string; min: number; max: number; color: string }[] = [
  { key: "fuel_level_pct", label: "FUEL", min: 0, max: 100, color: "#22c55e" },
  { key: "engine_rpm", label: "RPM", min: 0, max: 2300, color: "#22d3ee" },
  { key: "engine_temperature_c", label: "ENG T", min: 0, max: 120, color: "#f6a821" },
  { key: "hydraulic_pressure_bar", label: "HYD", min: 0, max: 260, color: "#a78bfa" },
  { key: "engine_load_pct", label: "LOAD", min: 0, max: 100, color: "#f472b6" },
  { key: "machine_speed_kph", label: "SPD", min: 0, max: 20, color: "#34d399" },
];

export function VitalsRail({ frames }: { frames: TelemetryFrame[] }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const framesRef = useRef(frames);
  framesRef.current = frames;

  useEffect(() => {
    let cancelled = false;
    let raf = 0;

    const paint = () => {
      const canvas = canvasRef.current;
      const wrap = wrapRef.current;
      if (!canvas || !wrap) return;

      const dpr = window.devicePixelRatio || 1;
      const w = wrap.clientWidth;
      const h = 168;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const data = framesRef.current.slice(-240);
      const laneH = h / LANES.length;
      const padR = 46;

      ctx.font = "9px ui-monospace, monospace";

      LANES.forEach((lane, i) => {
        const y0 = i * laneH;
        ctx.fillStyle = "#164e63";
        ctx.fillRect(0, y0, 2, laneH); // lane accent

        ctx.fillStyle = "rgba(148,163,184,0.55)";
        ctx.fillText(lane.label, 10, y0 + 12);

        // min / max reference marks
        const mid = y0 + laneH / 2;
        ctx.strokeStyle = "rgba(148,163,184,0.12)";
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.moveTo(0, mid);
        ctx.lineTo(w - padR, mid);
        ctx.stroke();
        ctx.setLineDash([]);

        // forecast / live sweep line
        ctx.strokeStyle = "rgba(34,211,238,0.14)";
        ctx.beginPath();
        ctx.moveTo(w - padR + 1, y0);
        ctx.lineTo(w - padR + 1, y0 + laneH);
        ctx.stroke();

        if (data.length < 2) return;
        const px = (v: number) => ((v - lane.min) / (lane.max - lane.min)) * (laneH - 10) + (y0 + 5);
        const step = (w - padR - 14) / (data.length - 1);

        ctx.strokeStyle = lane.color;
        ctx.shadowColor = lane.color;
        ctx.shadowBlur = 6;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        let i0 = -1;
        for (let j = 0; j < data.length; j++) {
          const x = 14 + step * j;
          const y = px(Number(data[j][lane.key]) || 0);
          if (i0 < 0) {
            ctx.moveTo(x, y);
            i0 = 0;
          } else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;

        const last = Number(data[data.length - 1][lane.key]) || 0;
        ctx.fillStyle = lane.color;
        ctx.fillText(last.toFixed(last < 100 ? 1 : 0), w - padR + 6, mid + 3);
      });
    };

    const loop = () => {
      if (cancelled) return;
      paint();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    const ro = new ResizeObserver(() => paint());
    if (wrapRef.current) ro.observe(wrapRef.current);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return (
    <div ref={wrapRef} className="w-full overflow-hidden">
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}