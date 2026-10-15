def test_filters_by_vehicle_and_status_newest_first(client, ids):
    body = client.get("/api/trips", params={"vehicle_id": str(ids["v1"]), "status": "COMPLETED"}).json()
    assert body["total"] == 3
    assert [t["id"] for t in body["items"]] == [str(ids["t3"]), str(ids["t2"]), str(ids["t1"])]
    first = body["items"][0]
    assert first["rider"]["name"] == "Carol Poor"
    assert first["vehicle"] == {"id": str(ids["v1"]), "license_plate": "RS90001", "vehicle_class": "ECONOMY"}
    assert first["next_status"] is None


def test_search_by_plate_or_name(client, ids):
    by_plate = client.get("/api/trips", params={"search": "RS90002"}).json()
    assert [t["id"] for t in by_plate["items"]] == [str(ids["t4"])]
    by_name = client.get("/api/trips", params={"search": "carol"}).json()
    assert [t["id"] for t in by_name["items"]] == [str(ids["t3"])]


def test_date_range_is_inclusive(client, ids):
    body = client.get("/api/trips", params={"from": "2026-06-02", "to": "2026-06-03"}).json()
    assert {t["id"] for t in body["items"]} == {str(ids["t4"]), str(ids["t2"])}


def test_active_filter(client, ids):
    body = client.get("/api/trips", params={"status": "ACTIVE", "rider_id": str(ids["bob"])}).json()
    assert [t["id"] for t in body["items"]] == [str(ids["bob_trip"])]


def test_detail_with_and_without_review(client, ids):
    with_review = client.get(f"/api/trips/{ids['t1']}").json()
    assert with_review["review"]["rating"] == 5
    assert with_review["review"]["tags"] == ["Clean Car", "Polite"]
    assert client.get(f"/api/trips/{ids['t3']}").json()["review"] is None


def test_status_moves_one_step_at_a_time(client, ids):
    url = f"/api/trips/{ids['bob_trip']}/status"
    skip = client.patch(url, json={"status": "COMPLETED"})
    assert skip.status_code == 409
    assert skip.json()["error"]["code"] == "INVALID_TRANSITION"
    assert "next allowed status is IN_TRANSIT" in skip.json()["error"]["message"]

    step1 = client.patch(url, json={"status": "IN_TRANSIT"})
    assert step1.status_code == 200
    assert step1.json()["status"] == "IN_TRANSIT"
    assert step1.json()["next_status"] == "COMPLETED"

    step2 = client.patch(url, json={"status": "COMPLETED"})
    assert step2.status_code == 200
    assert step2.json()["next_status"] is None

    again = client.patch(url, json={"status": "IN_TRANSIT"})
    assert again.status_code == 409
    assert "already COMPLETED" in again.json()["error"]["message"]


def test_status_errors(client):
    missing = client.patch("/api/trips/00000000-0000-0000-0000-000000000000/status", json={"status": "IN_TRANSIT"})
    assert missing.status_code == 404
    bad_value = client.patch("/api/trips/00000000-0000-0000-0000-000000000000/status", json={"status": "FLYING"})
    assert bad_value.status_code == 422
