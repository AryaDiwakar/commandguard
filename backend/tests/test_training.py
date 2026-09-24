"""Interactive training workflow tests."""
from __future__ import annotations

from app.training.service import TrainingService


def test_training_hides_answer_and_scores_safe_sequence():
    service = TrainingService()
    started = service.start("fuel_leak_response", "OP-01")
    assert "correct" not in started["step"]

    actions = ["REQUEST_HELP", "STOP_MACHINE", "SHUTDOWN_ENGINE", "VERIFY_AND_ESCALATE"]
    state = started
    for action in actions:
        state = service.act(state["session_id"], action)

    assert state["complete"] is True
    assert state["score"] == 100
    assert len(state["actions"]) == 4


def test_wrong_training_action_is_recorded_without_advancing():
    service = TrainingService()
    started = service.start("safe_reversing", "OP-02")
    state = service.act(started["session_id"], "INCREASE_SPEED")
    assert state["correct"] is False
    assert state["step_index"] == 0
    assert state["mistakes"] == 1


def test_recommendations_follow_incident_patterns():
    service = TrainingService()
    recommendations = service.recommendations([{"incident_type": "PROXIMITY_HAZARD"}])
    assert recommendations[0]["module_id"] == "safe_reversing"
