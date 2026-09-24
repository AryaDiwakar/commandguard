import { useEffect, useMemo, useState } from "react";

import { bootFleet, fleetOverview, operatorInput, resetDemo } from "../lib/api";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

const CHECKLIST = [
  ["SEATBELT", "Seatbelt is fastened before machine movement."],
  ["WORK ZONE", "The work zone and reversing path are clear or controlled."],
  ["CONDITIONS", "Weather, terrain, visibility, and slope have been reviewed."],
  ["ESCALATION", "I know how to request live assistance and stop safely."],
] as const;

type FleetMachine = Awaited<ReturnType<typeof fleetOverview>>["machines"][number];

const WALKTHROUGH: Array<[string, (live: Record<string, boolean>) => boolean]> = [
  ["Three machines boot and stream live telemetry", (live) => live["MX-101"] && live["MX-102"] && live["MX-103"]],
  ["Fuel leak drives fuel % toward the flag threshold", (live) => Boolean(live["MX-101"])],
  ["Alert fires with evidence + approved guidance", () => false],
  ["Operator responds: STOP safely / auto safe-stop", () => false],
  ["Verification: RPM=0, settled, then RESUME", () => false],
  ["Task 1 completes and rolls over to Task 2", () => false],
  ["LLM co-pilot answers from retrieved guidance", () => false],
];

export function PreStartPage({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [seatbeltFastened, setSeatbeltFastened] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [live, setLive] = useState<Record<string, boolean>>({});
  const { machineId, setSeatbeltStatus: setGlobalSeatbelt } = useTelemetry();
  const allChecked = CHECKLIST.every(([id]) => id === "SEATBELT" ? seatbeltFastened : checked[id]);

  const refreshLive = () => {
    fleetOverview()
      .then((result) => setLive(Object.fromEntries(result.machines.map((machine: FleetMachine) => [machine.machine_id, machine.live]))))
      .catch(() => undefined);
  };

  const startDemo = () => {
    setDemoOpen(true);
    bootFleet().then(refreshLive).catch(() => undefined);
  };

  const stopDemo = () => {
    resetDemo().then(() => setLive({})).catch(() => undefined);
  };

  useEffect(() => {
    if (!demoOpen) return;
    refreshLive();
    const timer = window.setInterval(refreshLive, 3000);
    return () => window.clearInterval(timer);
  }, [demoOpen]);

  const demoSteps = useMemo(() => WALKTHROUGH.map(([label, ready]) => ({ label, ready: ready(live) })), [live]);

  useEffect(() => {
    const onToggle = () => {
      setSeatbeltFastened((current) => !current);
    };
    window.addEventListener("cat-commandguard-seatbelt-toggle", onToggle);
    return () => window.removeEventListener("cat-commandguard-seatbelt-toggle", onToggle);
  }, []);

  const toggleSeatbelt = () => {
    setSeatbeltFastened((current) => {
      const next = !current;
      setGlobalSeatbelt(next ? "Fastened" : "Unfastened");
      return next;
    });
    operatorInput(machineId, "TOGGLE_SEATBELT").catch(() => undefined);
  };

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1100px] flex-col justify-center gap-4 p-4 sm:p-8">
      <header className="mb-2 flex items-end justify-between gap-4 px-1">
        <div><div className="hud-label text-cat">CAT COMMANDGUARD / BEFORE YOU START</div><h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-100 sm:text-5xl">Let&apos;s make the shift safe.</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-500">We&apos;ll do three quick checks before showing the machine controls. This is a synthetic practice environment, not a connection to physical equipment.</p></div>
        <div className="hidden text-right sm:block"><div className="num text-3xl text-cat">0{step + 1}</div><div className="hud-label">OF 03</div></div>
      </header>
      <div className="flex gap-1 px-1"><span className={"h-1 flex-1 rounded " + (step >= 0 ? "bg-cat" : "bg-carbon-700")} /><span className={"h-1 flex-1 rounded " + (step >= 1 ? "bg-cat" : "bg-carbon-700")} /><span className={"h-1 flex-1 rounded " + (step >= 2 ? "bg-cat" : "bg-carbon-700")} /></div>

      {step === 0 && <Panel title="01 / THE SAFE WAY" right={<span className="num text-[10px] text-good">1 MINUTE</span>} className="border-cat/30"><div className="grid gap-4 md:grid-cols-3"><div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-4"><div className="text-2xl text-good">◈</div><h2 className="mt-3 text-sm font-semibold text-slate-100">Look first</h2><p className="mt-2 text-xs leading-relaxed text-slate-500">Check the machine, the task, and the space around you before moving.</p></div><div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-4"><div className="text-2xl text-holo">⌁</div><h2 className="mt-3 text-sm font-semibold text-slate-100">Stop when unsure</h2><p className="mt-2 text-xs leading-relaxed text-slate-500">If something looks wrong, reduce load or stop safely and ask for help.</p></div><div className="rounded border border-carbon-700/70 bg-carbon-950/40 p-4"><div className="text-2xl text-cat">↗</div><h2 className="mt-3 text-sm font-semibold text-slate-100">Check the result</h2><p className="mt-2 text-xs leading-relaxed text-slate-500">CommandGuard checks the live signals to make sure your response worked.</p></div></div><button onClick={() => setStep(1)} className="mt-6 w-full rounded border border-cat/70 bg-cat/10 px-4 py-3 num text-xs font-semibold tracking-widest text-cat transition hover:bg-cat/20">I UNDERSTAND · NEXT</button></Panel>}

      {step === 1 && <Panel title="02 / CHECK BEFORE YOU MOVE" right={<span className="num text-[10px] text-warn">CHECK EACH ITEM</span>}><p className="mb-4 text-sm text-slate-400">Tap each box when it is true for your work area. For the seatbelt, press <b className="text-cat">S</b> or use the button.</p><div className="flex flex-col gap-2">{CHECKLIST.map(([id, label]) => id === "SEATBELT" ? <div key={id} className={"flex flex-wrap items-center justify-between gap-3 rounded border px-4 py-4 transition " + (seatbeltFastened ? "border-good/50 bg-good/5" : "border-danger/40 bg-danger/5")}><span><span className="num text-xs text-holo">{id}</span><span className="ml-3 text-sm text-slate-200">{label}</span></span><button onClick={toggleSeatbelt} className={"rounded border px-3 py-2 num text-[10px] font-semibold tracking-widest " + (seatbeltFastened ? "border-good/60 bg-good/10 text-good" : "border-danger/60 bg-danger/10 text-danger")}>S · BELT {seatbeltFastened ? "ON" : "OFF"}</button></div> : <label key={id} className={"flex cursor-pointer items-center gap-3 rounded border px-4 py-4 transition " + (checked[id] ? "border-good/50 bg-good/5" : "border-carbon-700/70 bg-carbon-950/30 hover:border-carbon-500")}><input type="checkbox" checked={Boolean(checked[id])} onChange={(event) => setChecked((current) => ({ ...current, [id]: event.target.checked }))} className="h-4 w-4 accent-yellow-400" /><span><span className="num text-xs text-holo">{id}</span><span className="ml-3 text-sm text-slate-200">{label}</span></span></label>)}</div><div className="mt-6 flex gap-2"><button onClick={() => setStep(0)} className="flex-1 rounded border border-carbon-600 px-4 py-3 num text-xs tracking-widest text-slate-400">BACK</button><button disabled={!allChecked} onClick={() => setStep(2)} className="flex-[2] rounded border border-cat/70 bg-cat/10 px-4 py-3 num text-xs font-semibold tracking-widest text-cat transition hover:bg-cat/20 disabled:cursor-not-allowed disabled:opacity-30">EVERYTHING CHECKED · NEXT</button></div></Panel>}

      {step === 2 && <Panel title="03 / YOUR SHIFT BRIEF" right={<span className="num text-[10px] text-good">READY</span>}><div className="grid gap-4 md:grid-cols-2"><div className="rounded border border-holo/30 bg-holo/5 p-4"><div className="hud-label text-holo">TODAY&apos;S WORK LOOP</div><div className="mt-3 flex flex-wrap items-center gap-2 num text-sm text-slate-200"><span>DIG</span><span className="text-holo">→</span><span>HAUL</span><span className="text-holo">→</span><span>REVERSE</span><span className="text-holo">→</span><span>DUMP</span></div><p className="mt-4 text-xs leading-relaxed text-slate-500">Your home screen will show what to do, how much time is left, and whether anything needs attention.</p></div><div className="rounded border border-good/30 bg-good/5 p-4"><div className="hud-label text-good">HELP IS READY</div><p className="mt-3 text-sm leading-relaxed text-slate-300">If a problem appears, CommandGuard explains it in plain language, contacts support, guides the safe response, and checks that the machine settles.</p></div></div>
      <div className="mt-6 grid gap-2">
        <button onClick={startDemo} className="w-full rounded border border-holo/70 bg-holo/10 px-4 py-3 num text-xs font-semibold tracking-widest text-holo transition hover:bg-holo/20">RUN 3-MACHINE DEMO WALKTHROUGH</button>
        {demoOpen && <Panel title="JUDGE MODE / WALKTHROUGH" right={<span className="num text-[10px] text-holo">LIVE CHECKLIST</span>}>
          <div className="mb-2 flex justify-between text-[10px] text-slate-500"><span>Boots MX-101/102/103 — follow the live story: degrade → alert → safe stop → verify → resume → task rollover → co-pilot.</span><button onClick={stopDemo} className="rounded border border-carbon-600 px-2 py-1 num tracking-widest text-slate-400 hover:border-danger/60 hover:text-danger">RESET</button></div>
          <div className="flex flex-col gap-1.5">{demoSteps.map((stepItem, index) => (
            <div key={index} className="flex items-center gap-2 rounded border border-carbon-700/60 px-3 py-2 text-xs"><span className={"h-2 w-2 shrink-0 rounded-full " + (stepItem.ready ? "bg-good" : "bg-slate-600")} /><span className={"text-slate-300" + (stepItem.ready ? "" : " opacity-70")}>{stepItem.label}</span><span className="ml-auto num text-[10px] text-slate-500">{stepItem.ready ? "READY" : "OPERATOR"}</span></div>
          ))}</div>
        </Panel>}
      </div>
      <button onClick={onComplete} className="mt-4 w-full rounded border border-good/70 bg-good/10 px-4 py-3 num text-xs font-semibold tracking-widest text-good transition hover:bg-good/20">START MY SHIFT</button></Panel>}

      <footer className="px-1 text-center text-[10px] uppercase tracking-[0.18em] text-slate-600">Synthetic operator support environment · Always follow site procedures and designated safety personnel</footer>
    </div>
  );
}
