def test_list_sorted_by_earnings_with_freshness(client, ids):
    body = client.get("/api/vehicles", params={"sort": "earnings", "search": "RS9000"}).json()
    plates = [v["license_plate"] for v in body["items"]]
    assert plates[:2] == ["RS90001", "RS90002"]  # 180.00 each, tie broken by plate
    assert body["items"][0]["total_earnings"] == 180.00
    assert body["items"][0]["lifetime_trip_count"] == 3
    assert body["stats_as_of"] is not None


def test_filters(client):
    xl = client.get("/api/vehicles", params={"class": "XL"}).json()
    assert [v["license_plate"] for v in xl["items"]] == ["RS90003"]
    inactive = client.get("/api/vehicles", params={"is_active": False}).json()
    assert [v["license_plate"] for v in inactive["items"]] == ["RS90003"]


def test_classes(client):
    assert client.get("/api/vehicles/classes").json() == ["ECONOMY", "POOL", "PREMIUM", "XL"]


def test_detail_includes_dense_rank(client, ids):
    v1 = client.get(f"/api/vehicles/{ids['v1']}").json()
    assert v1["revenue_rank"] == 1
    assert v1["total_earnings"] == 180.00
    v3 = client.get(f"/api/vehicles/{ids['v3']}").json()
    assert v3["revenue_rank"] is None  # no completed trips


def test_catalog_document_is_returned_generically(client, ids):
    doc = client.get(f"/api/vehicles/{ids['v1']}/metadata").json()
    assert "_id" not in doc
    assert doc["features"] == ["wifi", "child_seat"]
    assert doc["registration_city"] == "San Francisco"
    assert doc["inspection_records"][0]["passed"] is True
    assert doc["inspection_records"][0]["inspected_at"].startswith("2026-05-01")


def test_catalog_missing(client, ids):
    res = client.get(f"/api/vehicles/{ids['v2']}/metadata")
    assert res.status_code == 404
    assert "Catalog document" in res.json()["error"]["message"]
    assert client.get("/api/vehicles/00000000-0000-0000-0000-000000000000/metadata").status_code == 404
