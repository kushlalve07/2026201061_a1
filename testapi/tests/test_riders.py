def test_list_is_paged_on_the_server(client):
    first = client.get("/api/riders", params={"search": "Zed Paging", "page_size": 25}).json()
    assert first["total"] == 30
    assert len(first["items"]) == 25
    second = client.get("/api/riders", params={"search": "Zed Paging", "page_size": 25, "page": 2}).json()
    assert [r["name"] for r in second["items"]] == [f"Zed Paging {i:02d}" for i in range(25, 30)]


def test_search_and_active_trip(client, ids):
    body = client.get("/api/riders", params={"search": "bob"}).json()
    assert body["total"] == 1
    bob = body["items"][0]
    assert bob["id"] == str(ids["bob"])
    assert bob["active_trip"] == {"id": str(ids["bob_trip"]), "status": "REQUESTED"}


def test_has_active_trip_filter(client, ids):
    names = [r["name"] for r in client.get("/api/riders", params={"has_active_trip": True, "search": "Busy"}).json()["items"]]
    assert names == ["Bob Busy"]
    free = client.get("/api/riders", params={"has_active_trip": False, "search": "Alice"}).json()
    assert [r["name"] for r in free["items"]] == ["Alice Free"]


def test_search_treats_wildcards_literally(client):
    assert client.get("/api/riders", params={"search": "%"}).json()["total"] == 0


def test_page_size_is_capped(client):
    res = client.get("/api/riders", params={"page_size": 101})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rider_detail(client, ids):
    body = client.get(f"/api/riders/{ids['alice']}").json()
    assert body["name"] == "Alice Free"
    assert body["wallet_balance"] == 100.00
    assert body["active_trip"] is None
    # newest first: 06-05 (v4), 06-03 (v1), 06-01 (v1)
    assert [t["id"] for t in body["recent_trips"]] == [str(ids["t5"]), str(ids["t2"]), str(ids["t1"])]
    assert body["audit_entries"] == 1  # the opening-balance CREDIT


def test_rider_not_found_and_bad_id(client):
    missing = client.get("/api/riders/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    bad = client.get("/api/riders/not-a-uuid")
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["field"] == "path.rider_id"
