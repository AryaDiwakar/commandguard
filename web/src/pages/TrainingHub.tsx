import { useEffect, useState } from "react";

import { authMe, startTraining, trainingAction, trainingModules, trainingRecommendations } from "../lib/api";
import type { Principal, TrainingModule, TrainingState } from "../lib/types";
import { Panel } from "../components/Panel";

export function TrainingHubPage() {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [modules, setModules] = useState<TrainingModule[]>([]);
  const [recommendations, setRecommendations] = useState<Array<{ module_id: string; title: string; reason: string }>>([]);
  const [training, setTraining] = useState<TrainingState | null>(null);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    authMe().then((result) => setPrincipal(result.principal)).catch(() => undefined);
    trainingModules().then((result) => setModules(result.modules)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!principal) return;
    trainingRecommendations(principal.operator_id).then((result) => setRecommendations(result.recommendations)).catch(() => undefined);
  }, [principal]);

  const begin = (moduleId: string) => {
    if (!principal) return;
    startTraining(moduleId, principal.operator_id).then((state) => {
      setTraining(state);
      setFeedback(state.feedback);
    }).catch(() => undefined);
  };

  const act = (action: string) => {
    if (!training) return;
    trainingAction(training.session_id, action).then((state) => {
      setTraining(state);
      setFeedback(state.feedback);
    }).catch(() => undefined);
  };

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4 p-4">
      <header className="glass-panel flex flex-wrap items-end justify-between gap-4 px-5 py-5">
        <div>
          <div className="hud-label text-cat">OPERATOR TRAINING HUB / LIVE MODULES</div>
          <h1 className="mt-1 text-2xl font-semibold text-slate-100 sm:text-3xl">Operator decision training</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">Training modules and recommendations are loaded from the CommandGuard training service, not embedded page data.</p>
        </div>
        <div className="num text-right text-xs text-slate-500">{principal?.operator_id ?? "NO SESSION"}<br />{modules.length} MODULES</div>
      </header>

      {training ? (
        <Panel title={training.title} right={<span className="num text-[10px] text-holo">STEP {Math.min(training.step_index + 1, training.step_count)} / {training.step_count}</span>}>
          <div className="max-w-3xl">
            <div className="h-1.5 overflow-hidden rounded bg-carbon-700"><div className="h-full bg-gradient-to-r from-cat to-holo transition-all" style={{ width: `${(training.step_index / training.step_count) * 100}%` }} /></div>
            {training.complete ? (
              <div className="py-10 text-center">
                <div className="hud-label text-good">SIMULATION COMPLETE</div>
                <div className="mt-2 num text-5xl text-good">{training.score ?? "—"}</div>
                <div className="mt-2 text-sm text-slate-400">Score · {training.mistakes} incorrect actions · response sequence recorded</div>
                <button onClick={() => setTraining(null)} className="mt-5 rounded border border-holo/60 bg-holo/10 px-4 py-2 num text-xs tracking-widest text-holo">RETURN TO MODULES</button>
              </div>
            ) : (
              <>
                <div className="mt-8 hud-label text-holo">{training.step?.title}</div>
                <h2 className="mt-2 text-xl text-slate-100">{training.step?.prompt}</h2>
                <div className="mt-6 grid gap-2 sm:grid-cols-3">{training.step?.options.map((option) => <button key={option} onClick={() => act(option)} className="rounded border border-carbon-600/80 bg-carbon-800/50 px-3 py-4 text-left num text-xs text-slate-200 transition hover:border-cat/60 hover:bg-cat/10">{option.replace(/_/g, " ")}</button>)}</div>
                <div className={"mt-5 rounded border px-3 py-3 text-xs " + (training.correct === false ? "border-danger/40 text-danger" : "border-holo/30 text-slate-400")}>{feedback}</div>
              </>
            )}
          </div>
        </Panel>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_0.8fr]">
          <Panel title="RECOMMENDED FOR THIS OPERATOR" right={<span className="num text-[10px] text-cat">LIVE RECOMMENDATIONS</span>}>
            <div className="flex flex-col gap-2">
              {recommendations.length ? recommendations.map((recommendation) => <button key={recommendation.module_id} onClick={() => begin(recommendation.module_id)} className="rounded border border-cat/30 bg-cat/5 px-3 py-3 text-left transition hover:bg-cat/10"><div className="num text-sm text-cat">{recommendation.title}</div><div className="mt-1 text-xs text-slate-400">{recommendation.reason}</div></button>) : <div className="py-8 text-center text-sm text-slate-500">No recommendations available from the live training service.</div>}
            </div>
          </Panel>
          <Panel title="TRAINING MODULE CATALOG" right={<span className="num text-[10px] text-holo">{modules.length} MODULES</span>}>
            <div className="flex flex-col gap-2">{modules.map((module) => <button key={module.module_id} onClick={() => begin(module.module_id)} className="rounded border border-carbon-700/70 bg-carbon-950/30 px-3 py-3 text-left transition hover:border-holo/50"><div className="flex justify-between"><span className="text-sm font-medium text-slate-100">{module.title}</span><span className="num text-[10px] text-slate-500">{module.step_count} DECISIONS</span></div><div className="mt-1 text-xs text-slate-500">{module.description}</div></button>)}</div>
          </Panel>
        </div>
      )}
    </div>
  );
}
