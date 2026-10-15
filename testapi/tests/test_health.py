def test_health_reports_both_stores(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "postgres": "ok", "mongo": "ok"}


def test_unknown_route_uses_error_shape(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"
