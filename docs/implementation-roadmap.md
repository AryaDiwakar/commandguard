# Implementation Roadmap

The application is a standalone synthetic machine-operations platform. It does
not connect to physical machines or claim access to proprietary manufacturer
data.

## Implemented First Slice

- Correct scenario API defaults.
- Passing backend test baseline.
- Public telemetry serialization separated from hidden scenario truth.
- Bounded temporal telemetry state store.
- `TelemetrySource` contract and simulator adapter.
- Explainable fuel-loss detector using rolling observed signals.
- Incident model with evidence, confidence, severity, timeline, and lifecycle.
- Live-help relay endpoints.
- Simulated operator actions: stop, shutdown, reduce load, and resume.
- Telemetry-driven shutdown state transition.
- Main-page Live Help Relay glass panel.
- Multi-signal detectors for thermal, hydraulic, proximity, seatbelt, idle, unsafe-operation, sensor, electrical, and multi-factor risk.
- Explainable short-horizon risk forecasts and dynamic task ETA.
- Scenario catalog, live scenario injection controls, and synthetic daily task schedule API.
- Navigable Incident Center, Simulator, Tasks, Safety Center, and Training Hub surfaces.
- Interactive decision-based training sessions with mistake tracking and adaptive recommendations.
- API-backed safe-action procedures for the operator experience.
- Analytics overview API and glass Analytics page backed by persisted incident records.
- Durable public replay frames and restart-safe incident reports/replays.
- Grounded machine-aware assistant API and glass Assistant page.
- Task/operator performance analytics.
- `ReplayDataSource` and queue-backed `LiveDataSourceStub` adapters.
- Approved knowledge retrieval with citation-bearing assistant responses.
- Demo bearer authentication with operator, supervisor, maintenance, and admin roles.
- Opt-in read-only HTTP live telemetry gateway adapter.
- Command-center Dashboard with pre-start brief, shift handoff, What-If projection, trust layer, and deterministic demo controls.
- Maintenance handoff packet for escalation and investigation.
- Lightweight synthetic ETA regression with holdout evaluation metrics.
- Predictive snapshot with rolling pre-breach z-scores, component wear forecasts, behavior/fatigue scoring, pre-shift risk, and task productivity.
- Configurable task-output practice comparison across Eco, Balanced, High Productivity, and Aggressive profiles.
- Fleet supervisor overview, seatbelt keyboard/input control, runtime thresholds, and PDF incident export.

## Upcoming Vertical Slices

1. Replace demo authentication with an approved enterprise identity provider in deployment.
2. Add site-specific approved documentation to the knowledge index.
3. Connect an approved external live-source gateway behind the source contract.

## Runtime Boundary

```text
Data Source
  -> Telemetry State Store
  -> Intelligence Engine
  -> Evidence / Incident Manager
  -> Live Help Relay
  -> Operator UI
```

Synthetic scenario labels remain evaluation-only. Runtime detection consumes
observed telemetry and temporal evidence rather than injected scenario metadata.
