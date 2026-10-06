# Phase 1 — Foundations & Causal Simulator

Goal: a live telemetry environment where charts move at 1 Hz from a causally-generated
stream, with a verified test gate. Build blueprints (normal) and verifies (determinism,
conservation, schema conformance, situation derivation, live streaming).

## Delivered

1. **Canonical telemetry** (`backend/app/schemas/telemetry.py`)
   - `TelemetryFrame` (pydantic) covering the full agreed schema.
   - The challenge's 8 required columns preserved exactly: `Timestamp, Machine_ID,
     Operator_ID, Engine_Hours, Fuel_Used_L, Load_Cycles, Idling_Time_min,
     Seatbelt_Status, Safety_Alert_Triggered`, plus ~40 additive snake_case columns
     incl. ground-truth eval metadata (scenario_type/phase/anomaly/…).
   - `to_dict()` is JSON-safe for WS and REST.

2. **Physics-lite dynamics** (`backend/app/simulation/physics.py`)
   - First-order smoothing toward demand-driven targets; fuel is a conserved integral
     (`fuel_used = ∫ rate·dt`); thermal/hydraulic/electrical/motion models with
     correlated noise; cumulative counters (engine hours, cycles, idle minutes,
     position on a work-zone loop).

3. **Environment engine** (`environment.py`) — deterministic diurnal ambient curve,
   humidity/site terrain/visibility; placeholder state for Phase-2 weather events.

4. **Mission scheduler** (`mission.py`) — DIG → HAUL → REVERSE → DUMP work cycles with
   periodic breaks; deterministic from the session RNG.

5. **SimService + WS** (`simulation/service.py`, `ws/manager.py`) — one asyncio task per
   machine; pacing 1 `/speed` real second per frame; per-machine ring buffer; broadcast
   of `{frame, situation, events}`; REST control (`/api/simulation/*`, `/api/state`,
   `/api/onboard`, `/api/system/*`).

6. **Holo-Command frontend** (`web/`) — carbon canvas, glass panels, amber + cyan
   holography, scanline overlay; Live Machine page with ●LIVE indicator, digital machine
   environment shell, Vitals Rail (canvas time-trace with glow), Recharts telemetry
   charts, situation hero, and readout panels. WS client batches frames via
   `requestAnimationFrame`.

## Phase 1 gate (all passing)

- `test_physics` — fuel conservation (∫rate vs counter, rounding slack), fuel level vs
  integral, no-NaN + physical invariants across 120 frames, state↔signal correlation,
  engine-hours advance, 1-hour long-run stability.
- `test_determinism` — same seed ⇒ byte-identical stream; different seed ⇒ different.
- `test_schema` — required 8 columns present & typed; normal frame is clean; counters
  monotonic.
- `test_situation` — normal operation derives ACTIVE/HEALTHY/SAFE/LOW with confidence 1.0.
- `test_ws_integration` — session lifecycle, state endpoint returns frame+situation,
  live frames stream over `/ws/telemetry` with fuel monotonic.

```text
18 passed in ~1.5 s
```

## Notes / next phase

- Optional onboard endpoint exists (`/api/onboard`) for operator profile entry (Phase 1.5 UI).
- Tasks tables (`tasks`) and task-dataset generator arrive in Phase 2, wired to this schema.
- Scenario injectors (Phase 2) slot into `MachineGenerator.step()` between mission/environment
  and physics, mutating `cmd`/`params` — preserving all ODEs and counters built here.