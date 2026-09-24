import { useState } from "react";

import { askAssistant } from "../lib/api";
import type { AssistantReply } from "../lib/types";
import { Panel } from "../components/Panel";
import { useTelemetry } from "../store/useTelemetry";

type Message = { role: "operator" | "assistant"; text: string; reply?: AssistantReply };

export function AssistantPage() {
  const { machineId } = useTelemetry();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);

  const send = async (text = input) => {
    const prompt = text.trim();
    if (!prompt || busy) return;
    setInput("");
    setMessages((current) => [...current, { role: "operator", text: prompt }]);
    setBusy(true);
    try {
      const reply = await askAssistant(machineId, prompt);
      setMessages((current) => [...current, { role: "assistant", text: reply.message, reply }]);
    } finally {
      setBusy(false);
    }
  };

  return <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 p-4">
    <header className="glass-panel px-5 py-5"><div className="hud-label text-holo">AI ASSISTANT / MACHINE CONTEXT</div><h1 className="mt-1 text-2xl font-semibold text-slate-100">Ask the co-pilot what the machine knows.</h1><p className="mt-2 text-sm text-slate-500">Responses are grounded in current telemetry, derived situation, incident evidence, and approved safety guidance. The assistant does not invent sensor values.</p></header>
    <Panel title="CONTEXTUAL RELAY" right={<span className="num text-[10px] text-good">GROUNDED MODE</span>}>
      <div className="flex min-h-[340px] flex-col gap-3">
        {messages.length === 0 && <div className="flex flex-1 flex-col items-center justify-center text-center"><div className="text-4xl text-holo">◈</div><div className="mt-3 text-sm text-slate-300">Machine-aware assistance is ready.</div><div className="mt-2 flex flex-wrap justify-center gap-2"><button onClick={() => send("Why am I getting this warning?")} className="rounded border border-carbon-600 px-3 py-2 text-xs text-slate-400 hover:border-holo/60 hover:text-holo">Why is this warning showing?</button><button onClick={() => send("Is it safe to continue?")} className="rounded border border-carbon-600 px-3 py-2 text-xs text-slate-400 hover:border-holo/60 hover:text-holo">Is it safe to continue?</button><button onClick={() => send("What is my task ETA?")} className="rounded border border-carbon-600 px-3 py-2 text-xs text-slate-400 hover:border-holo/60 hover:text-holo">What is my task ETA?</button></div></div>}
        {messages.map((message, index) => <div key={`${message.role}-${index}`} className={"max-w-[88%] rounded border px-3 py-3 text-sm " + (message.role === "operator" ? "self-end border-cat/30 bg-cat/5 text-slate-200" : "border-holo/30 bg-holo/5 text-slate-300")}><div className="hud-label">{message.role === "operator" ? "OPERATOR" : "CO-PILOT"}</div><div className="mt-1 leading-relaxed">{message.text}</div>{message.reply && <><div className="mt-3 flex flex-wrap gap-2 border-t border-carbon-700/60 pt-2 text-[10px] text-slate-500"><span className="text-good">GROUNDED</span>{message.reply.sources.map((source) => <span key={source}>{source}</span>)}{message.reply.context?.active_incidents.map((incident) => <span key={incident} className="text-danger">{incident}</span>)}</div>{message.reply.knowledge?.map((document) => <div key={document.document_id} className="mt-2 rounded border border-holo/20 bg-carbon-950/30 px-2 py-2 text-[10px] text-slate-500"><span className="text-holo">{document.title}</span> · {document.source}</div>)}</>}</div>)}
        {busy && <div className="text-xs text-holo">Reading current machine context...</div>}
      </div>
      <div className="mt-4 flex gap-2 border-t border-carbon-700/70 pt-3"><input value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void send(); }} placeholder="Ask about the current machine state..." className="min-w-0 flex-1 rounded border border-carbon-600/80 bg-carbon-950/50 px-3 py-3 text-sm text-slate-200 outline-none focus:border-holo" /><button onClick={() => void send()} disabled={busy} className="rounded border border-holo/60 bg-holo/10 px-4 py-2 num text-xs tracking-widest text-holo disabled:opacity-50">SEND</button></div>
    </Panel>
  </div>;
}
