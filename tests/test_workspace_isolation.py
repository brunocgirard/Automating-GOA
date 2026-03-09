"""Per-user workspace isolation integration tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from src.utils.db import (
    create_project,
    get_client_by_quote_ref,
    load_machines_for_quote,
    save_client_info,
    save_machines_data,
)
from tests.helpers import login, unique_name


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "test-admin-password"


def test_workspace_isolation_with_admin_override() -> None:
    admin_client = TestClient(app)
    login(admin_client, ADMIN_USERNAME, ADMIN_PASSWORD)

    user1_client = TestClient(app)
    user2_client = TestClient(app)

    user1_username = unique_name("iso_user1")
    user2_username = unique_name("iso_user2")
    user_password = "workspace-pass-123"

    user1_register = user1_client.post(
        "/api/auth/register",
        json={"username": user1_username, "display_name": "Isolation User 1", "password": user_password},
    )
    assert user1_register.status_code == 201, user1_register.text
    user1_id = int(user1_register.json()["id"])

    user2_register = user2_client.post(
        "/api/auth/register",
        json={"username": user2_username, "display_name": "Isolation User 2", "password": user_password},
    )
    assert user2_register.status_code == 201, user2_register.text
    user2_id = int(user2_register.json()["id"])

    quote_ref_1 = unique_name("ISO-Q1")
    quote_ref_2 = unique_name("ISO-Q2")

    assert save_client_info({"quote_ref": quote_ref_1, "customer_name": "Iso Customer 1"}, owner_user_id=user1_id)
    assert save_client_info({"quote_ref": quote_ref_2, "customer_name": "Iso Customer 2"}, owner_user_id=user2_id)

    quote_1 = get_client_by_quote_ref(quote_ref_1)
    quote_2 = get_client_by_quote_ref(quote_ref_2)
    assert quote_1 is not None
    assert quote_2 is not None
    quote_1_id = int(quote_1["id"])
    quote_2_id = int(quote_2["id"])

    machines_payload = {
        "machines": [
            {
                "machine_name": "Isolation Machine",
                "main_item": {"description": "Main Isolation Machine", "item_price_numeric": 100000},
                "add_ons": [],
            }
        ],
        "common_items": [],
    }
    assert save_machines_data(quote_ref_1, machines_payload, owner_user_id=user1_id)
    assert save_machines_data(quote_ref_2, machines_payload, owner_user_id=user2_id)

    machine_1_rows = load_machines_for_quote(quote_ref_1)
    machine_2_rows = load_machines_for_quote(quote_ref_2)
    assert machine_1_rows
    assert machine_2_rows
    machine_1_id = int(machine_1_rows[0]["id"])
    machine_2_id = int(machine_2_rows[0]["id"])

    project_1 = create_project(
        {
            "project_name": unique_name("ISO Project 1"),
            "customer_name": "Iso Customer 1",
            "quote_ref": quote_ref_1,
        },
        owner_user_id=user1_id,
    )
    project_2 = create_project(
        {
            "project_name": unique_name("ISO Project 2"),
            "customer_name": "Iso Customer 2",
            "quote_ref": quote_ref_2,
        },
        owner_user_id=user2_id,
    )
    assert project_1 is not None
    assert project_2 is not None
    project_1_id = int(project_1["id"])
    project_2_id = int(project_2["id"])

    user1_quotes = user1_client.get("/api/quotes")
    assert user1_quotes.status_code == 200
    quote_refs_user1 = {row["quote_ref"] for row in user1_quotes.json()}
    assert quote_ref_1 in quote_refs_user1
    assert quote_ref_2 not in quote_refs_user1

    assert user1_client.get(f"/api/quotes/{quote_2_id}").status_code == 404
    assert user1_client.get(f"/api/machines/{machine_2_id}").status_code == 404
    assert user1_client.get(f"/api/shipping/{quote_2_id}/prefill").status_code == 404
    assert user1_client.get(f"/api/cor/{quote_2_id}/prefill").status_code == 404
    assert user1_client.get(f"/api/processing/machine-data/{machine_2_id}").status_code == 404
    assert user1_client.get(f"/api/processing/items/{quote_ref_2}").status_code == 404

    user1_projects = user1_client.get("/api/pm/projects")
    assert user1_projects.status_code == 200
    user1_project_ids = {int(row["id"]) for row in user1_projects.json()}
    assert project_1_id in user1_project_ids
    assert project_2_id not in user1_project_ids
    assert user1_client.delete(f"/api/pm/projects/{project_2_id}").status_code == 404

    user1_delete_own = user1_client.delete(f"/api/pm/projects/{project_1_id}")
    assert user1_delete_own.status_code == 200
    assert user1_client.get(f"/api/pm/projects/{project_1_id}").status_code == 404

    admin_quotes = admin_client.get("/api/quotes")
    assert admin_quotes.status_code == 200
    admin_quote_refs = {row["quote_ref"] for row in admin_quotes.json()}
    assert quote_ref_1 not in admin_quote_refs
    assert quote_ref_2 in admin_quote_refs

    assert admin_client.get(f"/api/machines/{machine_1_id}").status_code == 404
    assert admin_client.get(f"/api/machines/{machine_2_id}").status_code == 200
    assert admin_client.get(f"/api/shipping/{quote_1_id}/prefill").status_code == 404
    assert admin_client.get(f"/api/shipping/{quote_2_id}/prefill").status_code == 200

    admin_projects = admin_client.get("/api/pm/projects")
    assert admin_projects.status_code == 200
    admin_project_ids = {int(row["id"]) for row in admin_projects.json()}
    assert project_2_id in admin_project_ids

    admin_delete_user2 = admin_client.delete(f"/api/pm/projects/{project_2_id}")
    assert admin_delete_user2.status_code == 200
    assert admin_client.get(f"/api/pm/projects/{project_2_id}").status_code == 404
