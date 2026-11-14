def _upload(
    client, headers, name="n.txt", data=b"hello apollo", scope="personal", ctype="text/plain"
):
    return client.post(
        "/api/v1/documents",
        data={"scope": scope},
        files={"file": (name, data, ctype)},
        headers=headers,
    )


def test_documents_require_auth(client):
    assert client.get("/api/v1/documents", params={"scope": "personal"}).status_code == 401


def test_upload_then_ready(client, auth_header):
    r = _upload(client, auth_header())
    assert r.status_code == 202
    body = r.json()
    assert (body["status"], body["filename"], body["scope"]) == ("processing", "n.txt", "personal")
    # TestClient runs background tasks before returning, so processing is done.
    doc = client.get(f"/api/v1/documents/{body['id']}", headers=auth_header()).json()
    assert (doc["status"], doc["chunk_count"]) == ("ready", 1)


def test_upload_errors(client, auth_header):
    r = _upload(client, auth_header(), name="x.exe", data=b"MZ")
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file_type"
    r = _upload(client, auth_header(), name="big.txt", data=b"x" * (10 * 1024 * 1024 + 1))
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_invalid_scope_422(client, auth_header):
    assert _upload(client, auth_header(), scope="everyone").status_code == 422


def test_company_upload_forbidden_for_user(client, auth_header):
    r = _upload(client, auth_header(), scope="company")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_company_docs_listed_for_everyone(client, admin_header, bob_header):
    doc_id = _upload(client, admin_header, scope="company").json()["id"]
    listed = client.get("/api/v1/documents", params={"scope": "company"}, headers=bob_header)
    assert [d["id"] for d in listed.json()] == [doc_id]


def test_personal_listing_is_private(client, auth_header, bob_header):
    doc_id = _upload(client, auth_header()).json()["id"]
    mine = client.get("/api/v1/documents", params={"scope": "personal"}, headers=auth_header())
    theirs = client.get("/api/v1/documents", params={"scope": "personal"}, headers=bob_header)
    assert [d["id"] for d in mine.json()] == [doc_id]
    assert theirs.json() == []


def test_other_users_doc_404(client, auth_header, bob_header):
    doc_id = _upload(client, auth_header()).json()["id"]
    assert client.get(f"/api/v1/documents/{doc_id}", headers=bob_header).status_code == 404
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=bob_header).status_code == 404


def test_delete_204(client, auth_header, fake_vector_store):
    doc_id = _upload(client, auth_header()).json()["id"]
    r = client.delete(f"/api/v1/documents/{doc_id}", headers=auth_header())
    assert r.status_code == 204
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth_header()).status_code == 404
    assert fake_vector_store.ids("personal") == set()


def test_documents_when_vector_store_down(client, auth_header, fake_vector_store):
    fake_vector_store.available = False
    r = _upload(client, auth_header())
    assert r.status_code == 202
    doc = client.get(f"/api/v1/documents/{r.json()['id']}", headers=auth_header()).json()
    assert doc["status"] == "failed"
    r = client.delete(f"/api/v1/documents/{doc['id']}", headers=auth_header())
    assert r.status_code == 502 and r.json()["error"]["code"] == "vector_store_unavailable"


def test_health_reports_vector_store(client, fake_vector_store):
    assert client.get("/health").json()["vector_store"] == "ok"
    fake_vector_store.available = False
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok", "vector_store": "error"}


def test_health_does_not_wait_on_slow_vector_store(client, fake_vector_store):
    import time

    def blackholed_ping():
        time.sleep(5)
        return True

    fake_vector_store.ping = blackholed_ping
    started = time.perf_counter()
    r = client.get("/health")
    assert time.perf_counter() - started < 3.5
    assert r.status_code == 200
    assert r.json()["vector_store"] == "error"
