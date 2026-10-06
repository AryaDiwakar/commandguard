# CommandGuard — Smart Operator Assistant

> A digital co-pilot for heavy-machine operators: live telemetry, explainable risk,
> incident replay, operator training, and a grounded machine-aware assistant —
> all driven by a causal synthetic simulator.

**Software simulation only.** CommandGuard runs entirely on synthetic data. It is not
connected to any real machine, does not use proprietary manufacturer data, and does not
claim access to any real equipment telemetry.

---

## Why CommandGuard

Heavy-equipment operators make decisions under time pressure with imperfect information.
CommandGuard is a full-stack prototype of what an operator-facing decision support layer
looks like: every warning carries evidence, every incident can be replayed frame by frame,
and every recommendation is traceable back to observed signals — never to a black box.

## Highlights

- **Holo-Command UI** — carbon-canvas React dashboard with a live 1 Hz telemetry stream,
  holographic machine HUD, vitals rail, and Recharts telemetry plots over a WebSocket.
- **Causal simulator** — physics-lite dynamics (conserved fuel integral, thermal,
  hydraulic, electrical, motion), a deterministic diurnal environment, and a
  DIG → HAUL → REVERSE → DUMP mission scheduler. Same seed ⇒ byte-identical stream.
- **Explainable intelligence** — multi-signal detectors (thermal, hydraulic, proximity,
  seatbelt, idle, unsafe operation, sensor integrity, electrical, multi-factor) that emit
  incidents with evidence, confidence, severity, and a lifecycle — not just an alert flag.
- **Predictive layer** — rolling pre-breach z-scores, component wear forecasts,
  behavior/fatigue scoring, pre-shift risk, and short-horizon risk projections
  (continue / reduce load / stop).
- **Incident replay & handoff** — durable frame replay, generated incident reports,
  PDF export, and a maintenance handoff packet.
- **Operator training** — interactive decision modules with mistake tracking and
  adaptive recommendations driven by the live training service.
- **Grounded assistant** — RAG-style answers constrained to retrieved knowledge plus the
  live machine truth, with citations. It will not invent sensor values or numbers.
- **Roles & RBAC** — demo bearer auth with operator, supervisor, maintenance, and admin
  roles on top of an otherwise open local hackathon mode.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, NumPy, Pandas |
| Realtime | WebSockets (`/ws/telemetry`) + per-machine ring buffers |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts, Zustand |
| Storage | SQLite (portable demo DB; swap via `COMMANDGUARD_DB_URL`) |
| Deploy | Docker + Railway (API), Vercel (web) |
| Tests | Pytest (unit, integration, WebSocket, determinism) |

## Quick start

```bash
make install          # create .venv + install backend deps + npm install
make run-backend      # FastAPI on http://127.0.0.1:8000  (auto-reload)
# new terminal:
make run-web          # Vite dev on http://localhost:5173
```

Open <http://localhost:5173>. The **Pre-Start Safety** brief leads into the
**Dashboard**, and the **Live Machine** page streams telemetry at 1 Hz with the
Holo-Command HUD, vitals rail, charts, and the machine-situation hero.

## Verification

```bash
make test             # full backend pytest gate
make smoke            # serverless end-to-end check (session → WS → schema)
```

The gate covers physics conservation, determinism, schema conformance, situation
derivation, detectors/intelligence, scenario injection, product APIs, source contracts,
dataset splits, training, and live WebSocket streaming.

## Project layout

```text
backend/
  app/
    schemas/           canonical TelemetryFrame (+ required columns) and Machine Situation
    telemetry/         TelemetrySource contract + simulation / replay / live-stub adapters
    simulation/        physics · environment · mission · generator · catalog · SimService
    intelligence/      evidence engine, detectors, incidents, forecasts
    training/          interactive response training sessions
    knowledge/         approved document index + grounded LLM generation
    dataset/           synthetic task/corpus generators, splits, reports
    reports/           PDF incident export
    ws/manager.py      websocket broadcast manager
    api/               20 routers: system · simulation · state · onboard · incidents ·
                       tasks · training · safety · analytics · assistant · knowledge ·
                       auth · dashboard · what-if · demo · fleet · thresholds ·
                       operator · practice
    models.py / db.py  SQLAlchemy (telemetry · user_profiles · tasks)
  tests/               18 test modules — physics, determinism, schema, scenarios,
                       intelligence, sources, reliability, WS integration, …
web/                   Vite + React + TS + Tailwind (glass Holo-Command platform)
docs/                  phase1, implementation plan, implementation roadmap
Makefile               install · test · run-backend · run-web · smoke
Dockerfile             slim API image for Railway / any container host
```

## Data-mode contract

All telemetry flows through one boundary: the `TelemetrySource` contract
(`backend/app/telemetry/source.py`) producing the canonical `TelemetryFrame`.

| Mode | Status | Description |
| --- | --- | --- |
| `SIMULATION` | active default | Causal synthetic telemetry for demonstration |
| `REPLAY` | available | Persisted incident and historical telemetry replay |
| `LIVE_STUB` | available | Queue-backed contract adapter for integration tests |
| `LIVE` | opt-in, off | Read-only HTTP gateway adapter; requires approved deployment configuration |

All tuning values are clearly-labelled demo thresholds. Runtime detection consumes
observed telemetry and temporal evidence only — synthetic scenario labels are
evaluation-only and are never leaked to the runtime path.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `COMMANDGUARD_DB_URL` | `sqlite:///./data/commandguard.db` | SQLAlchemy database URL |
| `COMMANDGUARD_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `COMMANDGUARD_LLM_MODELS` | `llama3.2:3b,qwen2.5:3b` | Preferred local model order for the assistant |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Local LLM endpoint (assistant degrades gracefully without it) |

Demo credentials (only enforced when a bearer token is supplied):
`OP-01` / `SUP-01` / `MNT-01` / `ADMIN-01`, password `demo`.

## API surface

REST under `/api/*` (interactive docs at `/docs` when the backend is running):

```text
/api/system        status, data modes, disclaimer
/api/simulation    start · stop · status · scenario injection
/api/state         frame + derived machine situation
/api/incidents     evidence, reports, replay, live-help relay, PDF export
/api/tasks         synthetic schedule + ML ETA predictions
/api/practice      productivity/safety practice comparison
/api/what-if       continue / reduce-load / stop projections
/api/training      modules, sessions, recommendations
/api/analytics     incident and operator performance analytics
/api/assistant     grounded, citation-bearing answers
/api/knowledge     approved document retrieval
/api/fleet         supervisor view across machines
/api/auth          demo bearer tokens + role checks
/ws/telemetry      live frame stream ({frame, situation, events})
```

## Documentation

- [`docs/phase1.md`](docs/phase1.md) — foundations and causal simulator, plus the Phase 1 test gate
- [`docs/implementation-plan.md`](docs/implementation-plan.md) — locked live-demo decisions
- [`docs/implementation-roadmap.md`](docs/implementation-roadmap.md) — implemented slices and what comes next

## Disclaimer

CommandGuard is an independent software prototype. It simulates a generic heavy machine
with synthetic signals and demo thresholds. It is not affiliated with, endorsed by, or
connected to any equipment manufacturer, and it must not be used to operate real
equipment.
