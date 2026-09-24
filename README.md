# CAT Smart Operator Assistant

A digital co-pilot for heavy-machine operators. **Software simulation only** — it does
not connect to real Caterpillar hardware nor claim access to proprietary CAT data.

**Current milestone: Predictive hackathon prototype** — Command Center, Pre-Shift
Risk, Productivity Practice, Predictive Maintenance, Incident Replay, Analytics,
Training, Grounded Assistance, RBAC, and Opt-In Live Gateway Contracts.

## Quick start

```bash
make install          # create .venv (backend deps) + npm install (web)
make run-backend      # FastAPI on http://127.0.0.1:8000  (auto-reload)
# new terminal:
make run-web          # Vite dev on http://localhost:5173
```

Open http://localhost:5173 → the **Live Machine** page shows live telemetry at 1 Hz
with the Holo-Command HUD, the Vitals Rail, charts, and the machine situation hero.

## Verification

```bash
make test             # backend pytest gate
make smoke            # server-less end-to-end check (session → WS → schema)
```

## Layout

```
backend/
  app/
    schemas/telemetry.py     canonical TelemetryFrame (+ required columns)
    schemas/situation.py     derived Machine Situation
    telemetry/               source contract + simulation/replay/live-stub adapters
    intelligence/             evidence and incident engine
    training/                interactive response training
    simulation/              physics-lite dynamics · environment · mission · generator · SimService
    ws/manager.py            websocket broadcast manager
    api/                     system · simulation · state · incidents · tasks · safety · training · analytics · assistant · knowledge · auth
    models.py / db.py        SQLAlchemy (telemetry · user_profiles · tasks)
  tests/                     physics, determinism, schema, scenarios, intelligence, WS
web/                         Vite + React + TS + Tailwind (glass Holo-Command platform)
docs/phase1.md               what Phase 1 delivers and how it was verified
docs/implementation-roadmap.md current implementation and upcoming slices
```

## Data-mode contract

`app.simulation.service.SimService` currently consumes the simulator through the
`TelemetrySource` contract. Replay and future LIVE-stub adapters can use the same
boundary behind the same `TelemetryFrame`. All tuning values are clearly-labeled
demo thresholds.

See `docs/implementation-roadmap.md` for the current implementation boundary and
the upcoming vertical slices.
