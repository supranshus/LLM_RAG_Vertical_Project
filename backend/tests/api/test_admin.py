def test_admin_users_requires_token(client):
    assert client.get("/api/v1/admin/users").status_code == 401


def test_admin_users_forbidden_for_normal_user(client, auth_header):
    r = client.get("/api/v1/admin/users", headers=auth_header())
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_users_lists_with_counts(client, auth_header, admin_header):
    h = auth_header()
    cid = client.post("/api/v1/conversations", json={}, headers=h).json()["id"]
    client.post(f"/api/v1/conversations/{cid}/messages", json={"content": "hi"}, headers=h)

    r = client.get("/api/v1/admin/users", headers=admin_header)

    assert r.status_code == 200
    rows = {u["email"]: u for u in r.json()}
    alice = rows["alice@org"]
    assert (alice["conversation_count"], alice["message_count"]) == (1, 2)
    assert alice["display_name"] == "Alice"
    assert {"id", "created_at", "last_seen_at"} <= set(alice)
    assert (rows["admin@org"]["conversation_count"], rows["admin@org"]["message_count"]) == (0, 0)
