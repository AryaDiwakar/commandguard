import type { AppPage } from "../components/shell/AppShell";
import { Panel } from "../components/Panel";

export function ComingSoonPage({ page, onNavigate }: { page: AppPage; onNavigate: (page: AppPage) => void }) {
  return <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4"><Panel title={`${page.toUpperCase()} / NEXT OPERATING LAYER`}><div className="py-20 text-center"><div className="hud-label text-holo">MODULE SCAFFOLD READY</div><h1 className="mt-3 text-3xl font-semibold text-slate-100">This surface is connected to the same machine context.</h1><p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-slate-500">The intelligence engine, incident store, synthetic telemetry, and operator workflow are live. This module is the next UI layer in the roadmap.</p><button onClick={() => onNavigate("live")} className="mt-6 rounded border border-holo/60 bg-holo/10 px-4 py-2 num text-xs tracking-widest text-holo">RETURN TO LIVE MACHINE</button></div></Panel></div>;
}
