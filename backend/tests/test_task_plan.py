"""Demo task-plan regression: compressed first task, rollover, alert fields, ETA."""
from __future__ import annotations

from app.dataset.tasks import generate_shift_schedule
from app.intelligence.engine import IntelligenceEngine
from app.simulation.generator import DEMO_TASK_PLAN, MachineGenerator


def test_first_task_completes_within_demo_window_and_rolls_over():
    gen = MachineGenerator(seed=7)
    first_planned_s = gen.task_planned_s
    frames = [gen.step() for _ in range(int(first_planned_s) + 2)]

    completed = [f for f in frames if f.task_completed]
    assert len(completed) == 1
    boundary = completed[0]
    assert boundary.task_id == "EXC-0712"
    assert boundary.current_task_type == "EXCAVATION"
    assert boundary.completed_task_type == "EXCAVATION"
    assert boundary.next_task_type == "LOADING"
    assert boundary.task_status == "COMPLETED"
    assert boundary.task_progress_pct == 100.0
    assert boundary.task_planned_minutes == DEMO_TASK_PLAN[0]["planned_min"]

    settled = [f for f in frames if f.task_index == 1][0]
    assert settled.current_task_type == "LOADING"
    assert settled.task_status == "IN_PROGRESS"
    assert settled.task_progress_pct < 100.0


def test_last_task_completes_without_next_works():
    gen = MachineGenerator(seed=9)
    total_s = sum(entry["planned_min"] * 60.0 for entry in DEMO_TASK_PLAN)
    reached = False
    for _ in range(int(total_s) + 2):
        frame = gen.step()
        if frame.task_index == len(DEMO_TASK_PLAN) - 1 and frame.task_status == "COMPLETED":
            reached = True
            assert frame.next_task_type == ""
            assert frame.next_task_id == ""
            break
    assert reached


def test_eta_uses_demo_plan_minutes_and_stays_above_baseline():
    gen = MachineGenerator(seed=11)
    engine = IntelligenceEngine("MX-101")
    frame = gen.step()
    eta = engine.estimate_eta(frame)
    assert eta["baseline_minutes"] <= DEMO_TASK_PLAN[0]["planned_min"] + 0.5
    assert eta["eta_minutes"] >= eta["baseline_minutes"]


def test_eta_survives_rollover_to_next_task_type():
    gen = MachineGenerator(seed=13)
    engine = IntelligenceEngine("MX-101")
    frame = gen.step()
    while not frame.task_completed:
        frame = gen.step()
    rolled = gen.step()
    assert rolled.current_task_type in ("LOADING", "TRENCHING", "HAULING", "GRADING")
    eta = engine.estimate_eta(rolled)
    assert eta["eta_minutes"] >= 0
    assert eta["baseline_minutes"] <= rolled.task_planned_minutes + 0.5


def test_shift_schedule_is_demo_compressed_for_the_judging_window():
    tasks = generate_shift_schedule(machines=("MX-101",)).to_dict(orient="records")
    assert tasks[0]["Task_Type"] == "EXCAVATION"
    assert tasks[0]["Estimated_Time_min"] < 15.0
    assert all(row["Estimated_Time_min"] < 12.0 for row in tasks)