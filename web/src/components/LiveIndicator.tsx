export function LiveIndicator({ live }: { live: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded border border-carbon-600/70 bg-carbon-900/70 px-2.5 py-1 shadow-glow">
      <span className="relative flex h-2.5 w-2.5 items-center justify-center">
        {live && <span className="absolute inset-0 rounded-full bg-good/40 animate-pulseRing" />}
        <span className={"h-2 w-2 rounded-full " + (live ? "bg-good" : "bg-slate-600")} />
      </span>
      <span className={"num text-xs font-bold tracking-[0.3em] " + (live ? "text-good" : "text-slate-500")}>
        {live ? "LIVE" : "LINK"}
      </span>
    </div>
  );
}