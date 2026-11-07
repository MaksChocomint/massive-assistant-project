"""Интеграционные тесты REST API через TestClient."""

import pytest
from fastapi.testclient import TestClient


def first_user(client: TestClient) -> int:
    return int(client.get("/api/users").json()[0]["id"])


def intent_id(client: TestClient, code: str) -> int:
    items = client.get("/api/intents", params={"search": code}).json()["items"]
    return int(items[0]["id"])


# --- пользователи ------------------------------------------------------------------


def test_create_user(client: TestClient) -> None:
    response = client.post("/api/users", json={"username": "maria", "name": "Мария"})
    assert response.status_code == 201
    assert response.json()["username"] == "maria"
    assert client.get(f"/api/users/{response.json()['id']}").status_code == 200


def test_duplicate_username(client: TestClient) -> None:
    response = client.post("/api/users", json={"username": "ivan", "name": "Другой"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_validation_error_format(client: TestClient) -> None:
    response = client.post("/api/users", json={"username": "Bad Login!", "name": ""})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert {d["field"] for d in body["details"]} == {"body.username", "body.name"}


def test_user_not_found(client: TestClient) -> None:
    response = client.get("/api/users/999")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Пользователь 999 не найден"}
    }


# --- намерения -----------------------------------------------------------------------


def test_list_intents_with_pagination_and_sort(client: TestClient) -> None:
    first = client.get("/api/intents", params={"limit": 3, "sort": "name"}).json()
    assert first["total"] == 8
    assert len(first["items"]) == 3
    names = [i["name"] for i in first["items"]]
    assert names == sorted(names)
    second = client.get("/api/intents", params={"limit": 3, "offset": 3, "sort": "name"}).json()
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    assert all(i["utterances"] > 0 for i in first["items"])


def test_filter_intents(client: TestClient) -> None:
    scenarios = client.get("/api/scenarios").json()
    alarm = next(s for s in scenarios if s["code"] == "alarm")
    items = client.get("/api/intents", params={"scenario_id": alarm["id"]}).json()["items"]
    assert {i["code"] for i in items} == {"alarm_set", "alarm_query"}
    found = client.get("/api/intents", params={"search": "погод"}).json()["items"]
    assert [i["code"] for i in found] == ["weather_query"]


def test_intent_crud(client: TestClient) -> None:
    scenario_id = client.get("/api/scenarios").json()[0]["id"]
    body = {"code": "alarm_snooze", "name": "Отложить будильник", "scenario_id": scenario_id}
    created = client.post("/api/intents", json=body)
    assert created.status_code == 201
    new_id = created.json()["id"]

    assert client.post("/api/intents", json={**body, "name": "Ещё раз"}).status_code == 409
    patched = client.patch(f"/api/intents/{new_id}", json={"name": "Отложить", "is_active": False})
    assert patched.json()["name"] == "Отложить"
    assert patched.json()["is_active"] is False
    assert client.delete(f"/api/intents/{new_id}").status_code == 204
    assert client.get(f"/api/intents/{new_id}").status_code == 404


def test_intent_with_unknown_scenario(client: TestClient) -> None:
    response = client.post("/api/intents", json={"code": "x_y", "name": "Икс", "scenario_id": 999})
    assert response.status_code == 404


def test_delete_intent_in_use(client: TestClient) -> None:
    response = client.delete(f"/api/intents/{intent_id(client, 'general_joke')}")
    assert response.status_code == 409


def test_slot_types(client: TestClient) -> None:
    codes = {s["code"] for s in client.get("/api/slot-types").json()}
    assert {"time", "date", "food_type"} <= codes


# --- команды ---------------------------------------------------------------------------


def test_command_clarification_flow(client: TestClient) -> None:
    body = {"user_id": first_user(client), "text": "поставь будильник"}
    created = client.post("/api/commands", json=body)
    assert created.status_code == 201
    command = created.json()
    assert command["intent"] == "alarm_set"
    assert command["status"] == "needs_clarification"
    assert command["question"] == "На какое время поставить будильник?"

    bad = client.post(f"/api/commands/{command['id']}/clarify", json={"answer": "напиши музыку"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "business_rule"

    good = client.post(f"/api/commands/{command['id']}/clarify", json={"answer": "на семь утра"})
    assert good.status_code == 200
    assert good.json()["status"] == "completed"
    assert good.json()["question"] is None
    assert good.json()["slots"] == [{"slot": "time", "name": "Время", "value": "семь утра"}]

    again = client.post(f"/api/commands/{command['id']}/clarify", json={"answer": "в восемь утра"})
    assert again.status_code == 409


def test_cancel_command(client: TestClient) -> None:
    command = client.post(
        "/api/commands", json={"user_id": first_user(client), "text": "закажи еду"}
    ).json()
    assert client.post(f"/api/commands/{command['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/commands/{command['id']}/cancel").status_code == 409


def test_command_errors(client: TestClient) -> None:
    assert client.post("/api/commands", json={"user_id": 999, "text": "привет"}).status_code == 404
    assert client.post("/api/commands", json={"user_id": 1, "text": ""}).status_code == 422
    assert client.get("/api/commands/999").status_code == 404


def test_list_commands_with_filters(client: TestClient) -> None:
    uid = first_user(client)
    for text in ("поставь будильник", "разбуди меня в семь утра", "какая погода завтра"):
        client.post("/api/commands", json={"user_id": uid, "text": text})
    page = client.get("/api/commands", params={"status": "completed", "limit": 1}).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert client.get("/api/commands", params={"user_id": uid}).json()["total"] == 3
    assert client.get("/api/commands", params={"status": "unknown"}).status_code == 422


# --- аналитика и служебное -------------------------------------------------------------


def test_analytics(client: TestClient) -> None:
    uid = first_user(client)
    for text in ("поставь будильник", "разбуди меня в семь утра", "расскажи шутку"):
        client.post("/api/commands", json={"user_id": uid, "text": text})

    top = client.get("/api/analytics/top-intents", params={"limit": 1}).json()
    assert top[0]["intent"] == "alarm_set"
    assert top[0]["commands"] == 2
    assert top[0]["success_rate"] == 0.5

    summary = client.get("/api/analytics/status-summary").json()
    assert summary["total"] == 3
    assert summary["by_status"] == {"needs_clarification": 1, "completed": 2}

    days = client.get("/api/analytics/commands-by-day").json()
    assert sum(d["commands"] for d in days) == 3
    dataset = client.get("/api/analytics/dataset").json()
    assert sum(s["utterances"] for s in dataset) > 200


def test_train_nlu(client: TestClient) -> None:
    result = client.post("/api/nlu/train").json()
    assert result["trained_on"] > 200
    assert 0.5 < result["dev_accuracy"] <= 1


def test_health_and_ui(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert "/static/ui/assets/" in response.text
    assert client.get("/docs").status_code == 200
    assert client.get("/presentation").status_code == 200
    assert client.get("/history").status_code == 200


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/commands", {"user_id": 1, "text": "   "}),
        ("/api/users", {"username": "new_user", "name": " \t "}),
    ],
)
def test_whitespace_is_not_valid_input(client: TestClient, path: str, body: dict) -> None:
    response = client.post(path, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("field", ["name", "scenario_id", "is_active"])
def test_patch_cannot_clear_required_field(client: TestClient, field: str) -> None:
    iid = intent_id(client, "alarm_set")
    response = client.patch(f"/api/intents/{iid}", json={field: None})
    assert response.status_code == 422
    assert client.get(f"/api/intents/{iid}").json()[field] is not None


def test_invalid_sort_is_reported(client: TestClient) -> None:
    response = client.get("/api/intents", params={"sort": "unknown"})
    assert response.status_code == 422


def test_unknown_words_do_not_create_a_random_command(client: TestClient) -> None:
    before = client.get("/api/commands").json()["total"]
    response = client.post("/api/commands", json={"user_id": first_user(client), "text": "🤷"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "business_rule"
    assert client.get("/api/commands").json()["total"] == before
