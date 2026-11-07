from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Command, User


def populate(client: TestClient) -> dict:
    def create(text: str = "поставь будильник через минуту") -> dict:
        response = client.post("/api/dialogues", json={"text": text})
        assert response.status_code == 201
        return response.json()

    def confirm() -> dict:
        data = create()
        return client.post(f"/api/dialogues/{data['id']}/answer", json={"answer": "да"}).json()

    executed, failed, waiting = confirm(), confirm(), confirm()
    for data, success in ((executed, True), (failed, False)):
        response = client.post(
            f"/api/dialogues/{data['id']}/execution",
            json={"operation_id": f"op-{data['id']}", "success": success, "message": "Результат"},
        )
        assert response.status_code == 200
    clarifying = create("поставь будильник")
    cancelled = create()
    client.post(f"/api/dialogues/{cancelled['id']}/answer", json={"answer": "нет"})
    other_id = next(u["id"] for u in client.get("/api/users").json() if u["username"] == "ivan")
    legacy = client.post(
        "/api/commands", json={"user_id": other_id, "text": "разбуди меня в семь утра"}
    ).json()
    return {
        "executed": executed,
        "owner": executed["user"],
        "legacy": legacy,
        "waiting": waiting,
        "clarifying": clarifying,
    }


def test_empty_activity_is_valid(client: TestClient) -> None:
    assert client.get("/api/activity").json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
    data = client.get("/api/analytics/activity").json()
    assert data["total"] == 0
    assert data["execution_success_rate"] is None
    assert data["top_intents"] == data["by_user"] == data["by_day"] == []


def test_activity_counts_receipts_not_completed_status(client: TestClient) -> None:
    records = populate(client)
    summary = client.get("/api/analytics/activity").json()
    assert summary["total"] == 6
    assert summary["by_phase"] == {
        "executed": 1,
        "execution_failed": 1,
        "ready": 1,
        "clarifying": 1,
        "cancelled": 1,
        "legacy": 1,
    }
    assert summary["execution_success_rate"] == 0.5
    assert summary["top_intents"][0]["commands"] == 6
    assert summary["top_intents"][0]["executed"] == 1
    assert sum(day["commands"] for day in summary["by_day"]) == 6
    assert sum(day["executed"] for day in summary["by_day"]) == 1
    result = client.get("/api/activity", params={"phase": "executed"}).json()
    assert result["total"] == 1
    item = result["items"][0]
    assert item["id"] == records["executed"]["id"]
    assert item["execution_confirmed"] is True
    assert item["execution_message"] == "Результат"
    assert item["execution_recorded_at"] is not None
    assert item["user"]["name"] == "maksim ivanov"
    assert item["slots"][0]["value"] == "через минуту"
    legacy = client.get("/api/activity", params={"phase": "legacy"}).json()["items"][0]
    assert legacy["command_status"] == "completed"
    assert legacy["execution_confirmed"] is False
    assert legacy["execution_message"] is None
    assert legacy["execution_recorded_at"] is None


def test_activity_user_filter_scopes_history_and_summary(client: TestClient) -> None:
    records = populate(client)
    uid = records["owner"]["id"]
    history = client.get("/api/activity", params={"user_id": uid}).json()
    summary = client.get("/api/analytics/activity", params={"user_id": uid}).json()
    assert history["total"] == summary["total"] == 5
    assert all(c["user"]["id"] == uid for c in history["items"])
    assert len(summary["by_user"]) == 1
    assert summary["by_user"][0]["user_id"] == uid
    assert summary["by_user"][0]["executed"] == 1
    assert "legacy" not in summary["by_phase"]
    unknown = client.get("/api/activity", params={"user_id": 9999}).json()
    assert unknown["total"] == 0


def test_activity_pagination_and_literal_search(client: TestClient, loaded_db: Session) -> None:
    populate(client)
    pages = [
        client.get("/api/activity", params={"limit": 2, "offset": n}).json() for n in (0, 2, 4)
    ]
    ids = [c["id"] for p in pages for c in p["items"]]
    assert len(ids) == len(set(ids)) == 6
    assert all(p["total"] == 6 for p in pages)
    special = loaded_db.get(Command, ids[0])
    special.text += " %_проверка"
    loaded_db.commit()
    result = client.get("/api/activity", params={"search": "%_"}).json()
    assert result["total"] == 1
    assert result["items"][0]["id"] == special.id
    assert (
        client.get("/api/activity", params={"search": "не существующая фраза"}).json()["total"] == 0
    )


def test_activity_period_and_missing_receipts(client: TestClient, loaded_db: Session) -> None:
    records = populate(client)
    old = loaded_db.get(Command, records["executed"]["id"])
    old.created_at = datetime.now(UTC) - timedelta(days=10)
    loaded_db.commit()
    history = client.get("/api/activity", params={"days": 7}).json()
    summary = client.get("/api/analytics/activity", params={"days": 7}).json()
    assert history["total"] == summary["total"] == 5
    assert "executed" not in summary["by_phase"]
    assert summary["execution_success_rate"] == 0
    other = loaded_db.scalar(select(User).where(User.username == "ivan"))
    summary = client.get("/api/analytics/activity", params={"user_id": other.id}).json()
    assert summary["execution_success_rate"] is None
    assert summary["by_phase"] == {"legacy": 1}


@pytest.mark.parametrize(
    "params",
    [
        {"phase": "completed"},
        {"limit": 0},
        {"offset": -1},
        {"user_id": -1},
        {"days": 0},
        {"days": 366},
        {"search": "x" * 301},
    ],
)
def test_activity_rejects_invalid_filters(client: TestClient, params: dict) -> None:
    assert client.get("/api/activity", params=params).status_code == 422
