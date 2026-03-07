"""Integration tests for personal task board API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from tests.helpers import login, unique_name


def test_user_tasks_crud_and_owner_scope() -> None:
    user1_client = TestClient(app)
    user2_client = TestClient(app)

    user1_username = unique_name("tasks_user1")
    user2_username = unique_name("tasks_user2")
    user_password = "tasks-pass-123"

    register_user1 = user1_client.post(
        "/api/auth/register",
        json={"username": user1_username, "display_name": "Tasks User 1", "password": user_password},
    )
    assert register_user1.status_code == 201, register_user1.text
    login(user1_client, user1_username, user_password)

    register_user2 = user2_client.post(
        "/api/auth/register",
        json={"username": user2_username, "display_name": "Tasks User 2", "password": user_password},
    )
    assert register_user2.status_code == 201, register_user2.text
    login(user2_client, user2_username, user_password)

    created_response = user1_client.post(
        "/api/user-tasks",
        json={
            "title": "Email client about layout",
            "description": "Send updated draft and timeline",
            "client_tag": "SunPharma",
            "priority": "high",
            "due_date": "2026-03-10",
        },
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    task_id = int(created["id"])
    assert created["status"] == "pending"
    assert created["completed_at"] is None

    list_response = user1_client.get("/api/user-tasks")
    assert list_response.status_code == 200
    tasks = list_response.json()
    assert any(int(row["id"]) == task_id for row in tasks)

    tags_response = user1_client.get("/api/user-tasks/tags")
    assert tags_response.status_code == 200
    assert "SunPharma" in tags_response.json()

    toggle_response = user1_client.put(f"/api/user-tasks/{task_id}/toggle")
    assert toggle_response.status_code == 200, toggle_response.text
    toggled = toggle_response.json()
    assert toggled["status"] == "done"
    assert toggled["completed_at"]

    done_filter_response = user1_client.get("/api/user-tasks", params={"status": "done"})
    assert done_filter_response.status_code == 200
    done_ids = {int(row["id"]) for row in done_filter_response.json()}
    assert task_id in done_ids

    update_response = user1_client.put(
        f"/api/user-tasks/{task_id}",
        json={"status": "pending", "priority": "urgent", "client_tag": "Xeolas"},
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["status"] == "pending"
    assert updated["priority"] == "urgent"
    assert updated["client_tag"] == "Xeolas"
    assert updated["completed_at"] is None

    user2_list_response = user2_client.get("/api/user-tasks")
    assert user2_list_response.status_code == 200
    user2_ids = {int(row["id"]) for row in user2_list_response.json()}
    assert task_id not in user2_ids

    user2_update_response = user2_client.put(
        f"/api/user-tasks/{task_id}",
        json={"title": "Should not update"},
    )
    assert user2_update_response.status_code == 404

    user2_delete_response = user2_client.delete(f"/api/user-tasks/{task_id}")
    assert user2_delete_response.status_code == 404

    delete_response = user1_client.delete(f"/api/user-tasks/{task_id}")
    assert delete_response.status_code == 200
    assert delete_response.json().get("deleted") is True

    final_list_response = user1_client.get("/api/user-tasks")
    assert final_list_response.status_code == 200
    final_ids = {int(row["id"]) for row in final_list_response.json()}
    assert task_id not in final_ids
