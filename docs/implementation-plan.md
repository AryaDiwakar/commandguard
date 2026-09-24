# CommandGuard — Live-Demo Implementation Plan (Locked Decisions)

Status: APPROVED to execute, in order A → I. All file references verified against current code.

Goal: make every app surface reflect ONE live running simulation — no hardcoded/placeholder data — with a visible
"degrade → threshold → automatic reaction" loop for all 10 scenarios and coherent, model-derived numbers.

---

## A. Auto Safety-Override framework (all 10 scenarios)
Tiered per incident: DETECTED → CRITICAL → AUTO reaction. **Safe-stop only everywhere — never engine kill.**
- `backend/app/intelligence/engine.py` (top, imports ~1-12): detect somewhere a `pending_auto_actions()` per tick.
  - For each active incident, execute escalation rules: raise a `CRITICAL` tier and return `(action, reason)`.
  - Actions are existing generator commands only: `STOP_MACHINE` (forced engine-off *not* used; we keep safe-stop):
    actually for "safe-stop only everywhere": use `REDUCE_LOAD` and `STOP_MACHINE`. `STOP_MACHINE` halts motion
    (generator.py:151-152 applies state STOPPED, speed 0, rpm 0 — engine stays on). `SHUTDOWN_ENGINE` is the
    engine-kill — DO NOT auto-trigger it. Fuel-leak cutoff: rely on STOP + suppress? No — keep engine running:
    auto action for fuel = `STOP_MACHINE` + the incident's recommended action explains system secured tank. If we
    need tank drain stop, that is only via SHUTDOWN_ENGINE (`suppress_fuel_leak`) — DECIDED: do NOT use engine kill
    even for fuel. Use STOP + evidence; scenario naturally abates after `duration_s`. Reevaluate wording so copy says
    "machine protected / secured", not "engine cut".
- Bridge in `backend/app/simulation/service.py` `_emit` (~line 289-313): after `session.intelligence.observe(frame)`,
  for each queued auto action: `session.generator.apply_operator_action(action)` + `session.intelligence.record_action(action, incident_id)`
  (sets incident response_status) + append timeline event `AUTOMATIC_SAFETY_OVERRIDE` + broadcast `events` so UI shows it.
- Auto-verification flows through existing `_verify_response` (engine.py:368-377): STOP_MACHINE → verified when stationary
  & state in (STOPPED, SHUTDOWN). STOP keeps engine on → machine_state STOPPED → VERIFIED. Good.

### Per-scenario reaction (locked):
- FUEL_LEAK: DETECT (see B) → CRITICAL (excess ≥ ~1.0 %/min OR fuel_level ≤ 15%) → auto STOP_MACHINE.
- ENGINE_OVERHEAT: DETECT ≥98 C → CRITICAL ≥108 C → auto REDUCE_LOAD; sustained ≥112 C → auto STOP_MACHINE.
- HYDRAULIC_FAILURE: DETECT <75 bar@load → CRITICAL <50 bar → auto STOP_MACHINE.
- PROXIMITY_HAZARD: DETECT <8 m moving → CRITICAL <4 m moving → auto STOP_MACHINE.
- SEATBELT_VIOLATION: DETECT unfastened+moving → CRITICAL (moving unfastened >10 s) → auto STOP_MACHINE (safety hard constraint).
- EXCESSIVE_IDLE: DETECT ≥4 min idled → CRITICAL ≥8 min → auto REDUCE_LOAD? No — auto STOP_MACHINE is wrong for idle.
  DECIDED: idle economy → auto STOP_MACHINE keeps engine; better: auto "SHUTDOWN_ENGINE" is engine-kill. Keep engine on:
  auto STOP_MACHINE (engine idles at STOPPED rpm 0 load 0 — actually generator STOPPED sets rpm_norm 0 → rpm floor).
  Use consistent "safe-stop" language: machine placed in standby. FINE.
- UNSAFE_OPERATION: DETECT burst/harsh → CRITICAL (≥2 bursts in 60 s) → auto REDUCE_LOAD (governor).
- SENSOR_FAILURE: advisory only (no auto reaction — drift ≠ hazard).
- BATTERY_ANOMALY: DETECT <22 V → CRITICAL <20.5 V → auto REDUCE_LOAD; sustained → auto STOP_MACHINE.
- MULTI_FACTOR: CRITICAL by design → auto STOP_MACHINE.

## B. Fix + calibrate the scenario math (all 10 fire visibly)
- `_fuel_detection` (engine.py:217-239): rescale to avoid the dead threshold (currently never fires at 760 L tank).
  Use relative divergence: fire when `observed_loss > expected_loss * 1.25` AND `excess_rate_pct_min >= 0.2`
  (capacity-calibrated), window stays 20 frames.
- `FuelLeakInjector` (scenarios.py:181-190): raise leak so the drain is plainly visible: `fuel_leak_lph = (60 + 480*s) * e`
  → ~0.5-1 %/min sim drain on 760 L. Keep `fuel_rate_bias` small so reported rate stays plausible (divergence story holds).
- Verify remaining scenarios produce their detector within a demo window (overheat, hydraulic sag, proximity, seatbelt,
  idle ≥4 min, unsafe bursts, sensor consistency <0.98, battery <22 V, multi-factor). Adjust constants only if a
  detector can't fire (e.g., ensure hydraulic sag pressure <75 while load ≥70; battery <22 at severity 0.85; sensor
  drift consistently <0.98).
- **Headless harness**: `backend/tests/test_scenario_e2e.py` (new). For each of the 10 scenarios: start session speed 30,
  inject with onset 15/severity 0.85, step until DETECTED (≤ ~40 sim-s), assert auto action applied and response reaches
  VERIFIED. Runtime must stay < a few seconds per scenario.

## C. Staging UX (clicking must visibly do something)
- `web/src/components/ScenarioLab.tsx` (new): shared component with catalog select, severity, and a staged status strip:
  `STAGED — T−Xs → DETECTED → OVERRIDE/SECURED → RESOLVED` (poll `/api/simulation/status` + WebSocket events).
- Live Machine (OperationalContext.tsx:56) and Try a Scenario kiosk (Simulator.tsx) both render it.
- "AUTO SAFETY OVERRIDE ACTIVE — machine secured by CommandGuard" banner on LiveMachine + instrument delta readouts
  (fuel −X L/h, temp +X C/min) to make the degradation visible.
- Dashboard practice button reuses the same runner (G).

## D. Honest ETA (Estimated == ML Predicted == Active, via one model)
- `ml/eta.py`: add `predict_task(row: dict) -> float` reusing `_matrix` (1-row DataFrame, `round(max(15.0, values @ weights), 1)`).
- `api/tasks.py` `/today`: per record add `model_predicted_min`; top-level `model: eta_model().status.__dict__`.
- `web/src/lib/types.ts` (TaskSchedule line 144): add `model_predicted_min?`, `Reference_Time_min?`, `Machine_Age_yrs?`,
  `Rainfall_mmh?`, `Visibility_m?`; new `TaskModelStatus`.
- `web/src/lib/api.ts` (66-67): `todayTasks` returns `{ tasks, data_mode, model }`.
- `web/src/pages/Tasks.tsx`: capture model in effect; column (~line 257) → `(task.model_predicted_min ?? task.Estimated_Time_min).toFixed(1) min`;
  MAE tile (~line 179) → `±{model?.holdout_mae_minutes.toFixed(1) ?? "—"} min`.
- `intelligence/engine.py` `estimate_eta` (~:169): replace the constant 240-min baseline with the current scheduled task's
  planned duration (from shift schedule / planner scale) so Active ETA = `(100-progress)/100 × planned_total` reconciled
  with `predict_task` (full) × live weather/terrain/load modifiers. Keep the residual `eta_reasons`.
  Verify no test breaks (update if assertions on baseline exist).

## E. Live machine diagram (MachineHolo → telemetry)
- Wire `web/src/components/MachineHolo.tsx`: engine glow intensity↔engine_temperature_c, fuel fill↔fuel_level_pct,
  boom/bucket angle↔stage (DIG/HAUL/DUMP), seatbelt indicator, proximity radar rings↔proximity_distance_m,
  terrain tint↔terrain_condition. Feed live frame from `useTelemetry().latest`.

## F. Safety Center truth (no placeholder numbers masquerading as telemetry)
- `web/src/pages/SafetyCenter.tsx`: remove fake fallbacks (`:20` `|| !f`, `:24` `?? 14.5`, `:27` `?? 0`, `:30` `?? 0.08`,
  `:31` `?? 0.12`, `:35-39` CLEAR/DRY/3500/2.1) → render "WAITING FOR MACHINE" / dashes when `!f`.
- Drive flags + header from backend situation (`sit.safety_state`, `sit.active_incidents`, `sit.predicted_risks`,
  `sit.component_health`, `sit.current_risk`) instead of re-deriving thresholds client-side (single source of truth;
  header flips on overheat/hydraulic too).
- SOP section (`/api/safety/procedures`): add "STANDARD OPERATOR REFERENCE — static guidance" disclaimer; highlight the
  card that matches the current live active incident type; keep severities as reference tags only.
- "~ L wasted" (`:156`): replace `idlingMin * 0.05` constant with the machine's real idle fuel rate (frame
  `fuel_consumption_rate_lph` when idling, or `~0 L wasted` if not idling).

## G. Scenario entry points (unify behavior, keep all 3)
- `web/src/lib/api.ts`: `injectScenario(machineId, type, opts?: { severity?, onset_offset_s?, ramp_s? })` →
  POST full `ScenarioScript` body.
- `web/src/lib/scenario.ts` (new): `launchScenario({ machineId, type, severity = 0.85 })`:
  - no running session → `startSession({ speed: 5, scenario: { type, severity, onset_offset_s: 30 } })`;
  - session running → `injectScenario(machineId, type, { severity, onset_offset_s: 25, ramp_s: 8 })` (short onset so it
    visibly fires) and surface real-seconds countdown.
- Try a Scenario page (Simulator.tsx), Live Machine Scenario Lab (OperationalContext.tsx via LiveMachine.tsx:164), and
  Dashboard practice button (Dashboard.tsx:22) all call `launchScenario`.

## H. Analytics truth (live "TODAY" + labeled corpus history)
- `api/analytics.py` (~:46-68): remove seed-generated `generate_task_history` for the main panels. Provide LIVE/TODAY
  task metrics + operator performance derived from the running session (shift-schedule tasks, progress-derived
  estimated/actual/efficiency, live verified-response rate per operator). Incidents/metrics stay persisted-SQLite (real history).
- Secondary panel: "OFFLINE CORPUS — simulated history" fed from `data/phase2` summary (real generated files), clearly labeled.
- `web/src/pages/Analytics.tsx`: add 3 s auto-refresh (like Fleet.tsx:13); label panels LIVE/TODAY vs OFFLINE CORPUS.
- Keep model card copy tied to corpus.

## I. Fleet — run all 3 machines live
- Auto-start sessions for MX-101, MX-102 (QUARRY-NORTH), MX-103 (FOUNDATION-A) at app boot and on `/api/demo/reset`
  (deterministic per-machine seeds; default speed). Scenario/Safety demos stay focused on MX-101.
- Fleet (fleet.py already live) then shows 3 genuinely-LIVE machines with health/risk/ETA/behavior/incidents.
- Confirm 3 async loops (1 Hz) are fine and per-machine WebSocket topics broadcast correctly.
- Dashboard / Analytics focus stays MX-101 unless configurable.

---

## Verification (after every item)
- Backend: `cd backend && ../.venv/bin/python -m pytest` (must be 69 existing + new scenario e2e + predict_task green).
- Web: `cd web && npm run build` (chunk-size warning acceptable).
- Manual: `curl /api/tasks/today?machine_id=MX-101` shows `model_predicted_min` + `model`; inject fuel leak →
  STAGED → DETECTED (≤30 s) → auto override → VERIFIED; Fleet shows 3 LIVE; Safety Center shows REAL values, no placeholders.
- Live page-by-page walk of all 11 pages + both trigger paths.
- Demo state reset: `POST /api/demo/reset` before presenting; global S seatbelt flows; App.tsx preflight must NOT be reverted.

## Order & owners
A → B → C → D → E → F → G → H → I, each verified before moving on. All backend then web or interleaved per item.