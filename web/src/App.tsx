import { useEffect, useRef, useState } from "react";
import { AppShell, type AppPage } from "./components/shell/AppShell";
import { liveSituation, operatorInput } from "./lib/api";
import { useTelemetry } from "./store/useTelemetry";
import { ComingSoonPage } from "./pages/ComingSoon";
import { IncidentCenterPage } from "./pages/IncidentCenter";
import { AssistantPage } from "./pages/Assistant";
import { DashboardPage } from "./pages/Dashboard";
import { PreStartPage } from "./pages/PreStart";
import { LiveMachinePage } from "./pages/LiveMachine";
import { SafetyCenterPage } from "./pages/SafetyCenter";
import { TasksPage } from "./pages/Tasks";
import { TrainingHubPage } from "./pages/TrainingHub";
import { FleetPage } from "./pages/Fleet";
import { playAlertTone, toneForIncident } from "./lib/alertSound";

const validPages: AppPage[] = ["preflight", "dashboard", "tasks", "live", "safety", "incidents", "training", "fleet", "assistant"];

export default function App() {
  // Always start with safety precautions on every page refresh/load
  const [safetyCleared, setSafetyCleared] = useState(false);
  const [page, setPage] = useState<AppPage>("preflight");
  const { incident, seatbeltStatus, taskNotice, machineId, setMachine, setConnected, setSituation, pushFrames } = useTelemetry();
  const previousIncident = useRef<string | null>(null);
  const previousReaction = useRef<string | null>(null);
  const previousSeatbelt = useRef(seatbeltStatus);
  const previousTaskNotice = useRef<string | null>(null);
  const safetyClearedRef = useRef(safetyCleared);
  safetyClearedRef.current = safetyCleared;

  useEffect(() => {
    if (incident && incident.incident_id !== previousIncident.current) {
      // Auto safe-stop escalates to the critical climb; every scenario type
      // otherwise gets its own distinct cue (fuel, overheat, seatbelt, ...).
      playAlertTone(incident.auto_reaction ? "critical" : toneForIncident(incident.incident_type));
    }
    if (incident?.auto_reaction && incident.auto_reaction !== previousReaction.current) playAlertTone("critical");
    previousIncident.current = incident?.incident_id ?? previousIncident.current;
    previousReaction.current = incident?.auto_reaction ?? previousReaction.current;
  }, [incident]);

  useEffect(() => {
    if (previousSeatbelt.current === "Fastened" && seatbeltStatus === "Unfastened") playAlertTone("seatbelt");
    previousSeatbelt.current = seatbeltStatus;
  }, [seatbeltStatus]);

  useEffect(() => {
    if (taskNotice && taskNotice.completed_task_id !== previousTaskNotice.current) playAlertTone("verified");
    previousTaskNotice.current = taskNotice?.completed_task_id ?? previousTaskNotice.current;
  }, [taskNotice]);

  useEffect(() => {
    // Clear any previous persistent storage so refreshing always brings up the safety precaution
    try {
      window.localStorage.removeItem("cat-commandguard-preflight-v1");
    } catch {
      // Ignore if localStorage unavailable
    }
  }, []);

  useEffect(() => {
    const onGlobalSeatbelt = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key.toLowerCase() !== "s" || target?.tagName === "INPUT" || target?.tagName === "SELECT" || target?.isContentEditable) return;
      event.preventDefault();
      const current = useTelemetry.getState().seatbeltStatus;
      useTelemetry.getState().setSeatbeltStatus(current === "Fastened" ? "Unfastened" : "Fastened");
      window.dispatchEvent(new CustomEvent("cat-commandguard-seatbelt-toggle"));
      operatorInput(useTelemetry.getState().machineId, "TOGGLE_SEATBELT").catch(() => undefined);
    };
    window.addEventListener("keydown", onGlobalSeatbelt);
    return () => window.removeEventListener("keydown", onGlobalSeatbelt);
  }, []);

  useEffect(() => {
    const fromHash = (): AppPage | null => {
      const raw = window.location.hash.replace(/^#\/?/, "").trim();
      return (validPages.find((item) => item === raw) ?? null) as AppPage | null;
    };
    // Deep-link restore: a bookmarked #/live opens directly; otherwise preflight.
    const initial = fromHash();
    if (initial && initial !== "preflight") {
      setSafetyCleared(true);
      setPage(initial);
    }
    const onHashChange = () => {
      const next = fromHash();
      if (!next) return;
      if (next === "preflight") {
        setSafetyCleared(false);
        setPage("preflight");
      } else if (safetyClearedRef.current) {
        setPage(next);
      } else {
        window.location.hash = "preflight";
      }
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    window.location.hash = safetyCleared ? page : "preflight";
  }, [page, safetyCleared]);

  // Global store pump: keep the current machine's situation + frames warm on
  // every page so Home/Fleet/Assistant never render empty and alert chimes fire
  // regardless of which page mounted the live screen.
  useEffect(() => {
    let disposed = false;
    const poll = () => {
      liveSituation(machineId)
        .then((state) => {
          if (disposed) return;
          if (state.frame) {
            pushFrames([state.frame]);
            setConnected(true);
          }
          if (state.situation) setSituation(state.situation);
        })
        .catch(() => {
          if (!disposed) setConnected(false);
        });
    };
    poll();
    const timer = window.setInterval(poll, 1500);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [machineId, pushFrames, setConnected, setSituation]);

  const navigate = (next: AppPage) => {
    if (!validPages.includes(next)) return;
    if (next === "preflight") {
      setSafetyCleared(false);
      setPage("preflight");
      return;
    }
    if (!safetyCleared) return;
    setPage(next);
  };

  const openMachine = (id: string) => {
    setMachine(id);
    setPage("live");
  };

  const completePreflight = () => {
    setSafetyCleared(true);
    setPage("dashboard");
  };

  const content = (!safetyCleared || page === "preflight") ? (
    <PreStartPage onComplete={completePreflight} />
  ) : page === "live" ? (
    <LiveMachinePage />
  ) : page === "dashboard" ? (
    <DashboardPage />
  ) : page === "fleet" ? (
    <FleetPage onOpenMachine={openMachine} />
  ) : page === "assistant" ? (
    <AssistantPage />
  ) : page === "incidents" ? (
    <IncidentCenterPage />
  ) : page === "tasks" ? (
    <TasksPage />
  ) : page === "safety" ? (
    <SafetyCenterPage />
  ) : page === "training" ? (
    <TrainingHubPage />
  ) : (
    <ComingSoonPage page={page} onNavigate={navigate} />
  );

  return (
    <AppShell activePage={(!safetyCleared || page === "preflight") ? "preflight" : page} onNavigate={navigate} safetyCleared={safetyCleared}>
      {content}
    </AppShell>
  );
}
