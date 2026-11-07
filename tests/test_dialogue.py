"""Граница между собранной командой и подтверждённым внешним действием."""

import pytest
from fastapi.testclient import TestClient


def start(client: TestClient, text: str = "поставь будильник") -> dict:
    response = client.post("/api/dialogues", json={"text": text})
    assert response.status_code == 201
    return response.json()


def ready(client: TestClient) -> dict:
    session = start(client)
    response = client.post(f"/api/dialogues/{session['id']}/answer", json={"answer": "семь утра"})
    assert response.status_code == 200
    assert response.json()["phase"] == "awaiting_confirmation"
    return client.post(f"/api/dialogues/{session['id']}/answer", json={"answer": "да"}).json()


def test_dialogue_does_not_require_user_selection(client: TestClient) -> None:
    session = start(client)
    assert session["phase"] == "clarifying"
    assert session["spoken_text"] == "На какое время поставить будильник?"
    assert "user_id" not in session
    assert session["user"]["username"] == "maksim_ivanov"
    assert session["user"]["name"] == "maksim ivanov"
    assert session["execution_confirmed"] is False
    assert session["ready_for_execution"] is False


def test_filled_slots_require_explicit_confirmation(client: TestClient) -> None:
    session = start(client, "разбуди меня в семь утра")
    assert session["phase"] == "awaiting_confirmation"
    assert "семь утра" in session["spoken_text"]
    assert "да" in session["question"]
    assert session["ready_for_execution"] is False
    assert session["execution_confirmed"] is False


def test_one_minute_alarm_is_ready_for_confirmation(client: TestClient) -> None:
    session = start(client, "поставь будильник через минуту")
    assert session["phase"] == "awaiting_confirmation"
    assert [(s["slot"], s["value"]) for s in session["slots"]] == [("time", "через минуту")]
    assert session["execution_confirmed"] is False


def test_ready_does_not_mean_alarm_was_set(client: TestClient) -> None:
    session = ready(client)
    assert session["phase"] == "ready"
    assert session["ready_for_execution"] is True
    assert session["execution_confirmed"] is False
    assert "Вы подтвердили команду." in session["spoken_text"]
    assert "В демо" not in session["spoken_text"]
    assert "не подтверждено" not in session["spoken_text"]
    assert session["operation_id"] is None


def test_execution_receipt_is_required_and_idempotent(client: TestClient) -> None:
    session = ready(client)
    path = f"/api/dialogues/{session['id']}/execution"
    receipt = {
        "operation_id": "alarm-test-42",
        "success": True,
        "message": "Тестовый исполнитель подтвердил 07:00",
    }
    first = client.post(path, json=receipt)
    assert first.status_code == 200
    assert first.json()["phase"] == "executed"
    assert first.json()["execution_confirmed"] is True
    assert first.json()["execution_message"] == receipt["message"]
    assert client.post(path, json=receipt).json() == first.json()
    assert client.post(path, json={**receipt, "message": "другой результат"}).status_code == 409


def test_receipt_cannot_bypass_user_confirmation(client: TestClient) -> None:
    session = start(client, "разбуди меня в семь утра")
    response = client.post(
        f"/api/dialogues/{session['id']}/execution",
        json={"operation_id": "x", "success": True, "message": "готово"},
    )
    assert response.status_code == 409
    assert client.get(f"/api/dialogues/{session['id']}").json()["execution_confirmed"] is False


def test_execution_error_is_not_reported_as_success(client: TestClient) -> None:
    session = ready(client)
    response = client.post(
        f"/api/dialogues/{session['id']}/execution",
        json={"operation_id": "timeout-1", "success": False, "message": "Устройство не ответило"},
    )
    assert response.json()["phase"] == "execution_failed"
    assert response.json()["execution_confirmed"] is False
    assert "Устройство не ответило" in response.json()["spoken_text"]


def test_rejection_cancels_before_handoff(client: TestClient) -> None:
    session = start(client, "разбуди меня в семь утра")
    response = client.post(f"/api/dialogues/{session['id']}/answer", json={"answer": "нет"})
    assert response.json()["phase"] == "cancelled"
    assert response.json()["ready_for_execution"] is False


def test_invalid_time_can_be_corrected(client: TestClient) -> None:
    session = start(client)
    path = f"/api/dialogues/{session['id']}"
    assert client.post(path + "/answer", json={"answer": "не знаю"}).status_code == 400
    assert client.get(path).json()["phase"] == "clarifying"
    fixed = client.post(path + "/answer", json={"answer": "семь утра"})
    assert fixed.json()["phase"] == "awaiting_confirmation"


@pytest.mark.parametrize("in_initial_command", [False, True])
def test_spoken_hours_and_minutes_are_preserved(
    client: TestClient, in_initial_command: bool
) -> None:
    time = "семь часов десять минут"
    session = start(
        client, f"поставь будильник на {time}" if in_initial_command else "поставь будильник"
    )
    if not in_initial_command:
        response = client.post(f"/api/dialogues/{session['id']}/answer", json={"answer": time})
        assert response.status_code == 200
        session = response.json()
    assert session["intent"] == "alarm_set"
    assert session["phase"] == "awaiting_confirmation"
    assert [(slot["slot"], slot["value"]) for slot in session["slots"]] == [("time", time)]
    assert time in session["spoken_text"]


def test_attempt_limit_is_announced_as_failure(client: TestClient) -> None:
    session = start(client)
    path = f"/api/dialogues/{session['id']}"
    for _ in range(3):
        client.post(path + "/answer", json={"answer": "не знаю"})
    current = client.get(path).json()
    assert current["phase"] == "failed"
    assert current["execution_confirmed"] is False
    assert "Не удалось" in current["spoken_text"]


@pytest.mark.parametrize("text", ["поставь будильник", "разбуди меня в семь утра"])
def test_cancel_before_execution(client: TestClient, text: str) -> None:
    session = start(client, text)
    path = f"/api/dialogues/{session['id']}/cancel"
    assert client.post(path).json()["phase"] == "cancelled"
    assert client.post(path).status_code == 409


def test_confirmation_must_be_unambiguous(client: TestClient) -> None:
    session = start(client, "разбуди меня в семь утра")
    path = f"/api/dialogues/{session['id']}"
    assert client.post(path + "/answer", json={"answer": "наверное"}).status_code == 400
    assert client.get(path).json()["phase"] == "awaiting_confirmation"


def test_ready_cannot_be_cancelled_silently(client: TestClient) -> None:
    session = ready(client)
    path = f"/api/dialogues/{session['id']}"
    assert client.post(path + "/cancel").status_code == 409
    assert client.post(path + "/answer", json={"answer": "ещё"}).status_code == 409


def test_unknown_dialogue_and_whitespace(client: TestClient) -> None:
    assert client.get("/api/dialogues/99999").status_code == 404
    assert client.post("/api/dialogues", json={"text": "   "}).status_code == 422
    assert (
        client.post(
            "/api/dialogues/99999/execution",
            json={"operation_id": "x", "success": True, "message": "тест"},
        ).status_code
        == 404
    )
