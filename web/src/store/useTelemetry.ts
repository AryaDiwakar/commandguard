import { create } from "zustand";

import type { Incident, MachineSituation, TelemetryFrame } from "../lib/types";
import { DEFAULT_MACHINE_ID } from "../lib/config";

export interface TaskNotice {
  completed_task_id: string;
  completed_task_type: string;
  next_task_id: string;
  next_task_type: string;
}

interface TelemetryState {
  machineId: string;
  connected: boolean;
  latest: TelemetryFrame | null;
  situation: MachineSituation | null;
  incident: Incident | null;
  scenarioType: string | null;
  seatbeltStatus: "Fastened" | "Unfastened";
  frames: TelemetryFrame[];
  lastTaskIndex: number;
  taskNotice: TaskNotice | null;
  setMachine: (id: string) => void;
  setConnected: (v: boolean) => void;
  setSituation: (s: MachineSituation) => void;
  setIncident: (incident: Incident | null) => void;
  setScenarioType: (scenarioType: string | null) => void;
  setSeatbeltStatus: (status: "Fastened" | "Unfastened") => void;
  pushFrames: (frames: TelemetryFrame[]) => void;
  clearTaskNotice: () => void;
  reset: () => void;
}

const MAX_POINTS = 220;

export const useTelemetry = create<TelemetryState>((set) => ({
  machineId: DEFAULT_MACHINE_ID,
  connected: false,
  latest: null,
  situation: null,
  incident: null,
  scenarioType: null,
  // Pre-start begins unconfirmed; the operator must explicitly fasten it.
  seatbeltStatus: "Unfastened",
  frames: [],
  lastTaskIndex: -1,
  taskNotice: null,
  setMachine: (machineId) =>
    set({ machineId, latest: null, frames: [], situation: null, incident: null, lastTaskIndex: -1, taskNotice: null }),
  setConnected: (connected) => set({ connected }),
  setSituation: (situation) => set({ situation }),
  setIncident: (incident) => set({ incident }),
  setScenarioType: (scenarioType) => set({ scenarioType, incident: null, taskNotice: null, lastTaskIndex: -1 }),
  setSeatbeltStatus: (seatbeltStatus) => set({ seatbeltStatus }),
  pushFrames: (incoming) =>
    set((s) => {
      if (incoming.length === 0) return s;
      // Dedupe WS frames against polling snapshots by timestamp so charts and
      // sample counters never double-count the same sim frame.
      const seen = new Set<number>();
      for (const frame of s.frames) seen.add(frame.timestamp_ms);
      const fresh = incoming.filter((frame) => !seen.has(frame.timestamp_ms));
      if (fresh.length === 0) return s;
      const last = fresh[fresh.length - 1];
      let taskNotice = s.taskNotice;
      if (s.lastTaskIndex >= 0 && typeof last.task_index === "number" && last.task_index > s.lastTaskIndex) {
        taskNotice = {
          completed_task_id: last.completed_task_id ?? last.task_id,
          completed_task_type: last.completed_task_type ?? last.current_task_type,
          next_task_id: last.next_task_id,
          next_task_type: last.next_task_type,
        };
      }
      return {
        frames: [...s.frames, ...fresh].slice(-MAX_POINTS),
        latest: last,
        lastTaskIndex: typeof last.task_index === "number" ? last.task_index : s.lastTaskIndex,
        taskNotice,
        seatbeltStatus: last.Seatbelt_Status === "Unfastened" ? "Unfastened" : "Fastened",
      };
    }),
  clearTaskNotice: () => set({ taskNotice: null }),
  reset: () =>
    set({ frames: [], latest: null, situation: null, incident: null, scenarioType: null, seatbeltStatus: "Fastened", lastTaskIndex: -1, taskNotice: null }),
}));
