from tests.seed import ORIGIN

LNG, LAT = ORIGIN


def nearby(client, **params):
    return client.get("/api/map/nearby-vehicles", params={"lng": LNG, "lat": LAT, **params})


def test_nearest_first_one_row_per_vehicle(client, ids):
    body = nearby(client).json()
    assert body["radius_m"] == 5000
    items = body["items"]
    assert [i["license_plate"] for i in items] == ["RS90001", "RS90002"]
    # v1 has two pings (~100 m and ~300 m): only the nearest is kept
    assert 95 < items[0]["distance_m"] < 105
    assert 990 < items[1]["distance_m"] < 1010
    assert items[0]["location"]["lat"] > LAT


def test_radius_and_limit(client):
    assert [i["license_plate"] for i in nearby(client, radius_m=500).json()["items"]] == ["RS90001"]
    assert len(nearby(client, limit=1).json()["items"]) == 1


def test_validation(client):
    assert nearby(client, lat=100).status_code == 422
    assert nearby(client, radius_m=50000).status_code == 422


def test_simulated_pings_show_up(client, ids):
    res = client.post("/api/map/pings/simulate", json={"lng": LNG, "lat": LAT, "count": 3})
    assert res.status_code == 201
    simulated = res.json()["vehicle_ids"]
    assert res.json()["inserted"] == 3
    active = {str(ids[k]) for k in ("v1", "v2", "v4", "v5")}
    assert set(simulated) <= active
    found = {i["vehicle_id"] for i in nearby(client, limit=10).json()["items"]}
    assert set(simulated) <= found
