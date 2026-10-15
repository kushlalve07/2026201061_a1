def test_facet_summary_for_all_reviews(client):
    body = client.get("/api/reviews/summary").json()
    assert body["total"] == 3
    assert body["overall_average"] == 3.67
    assert body["rating_distribution"] == [
        {"rating": 1, "count": 0},
        {"rating": 2, "count": 1},
        {"rating": 3, "count": 0},
        {"rating": 4, "count": 1},
        {"rating": 5, "count": 1},
    ]
    assert body["top_tags"] == [
        {"tag": "Clean Car", "count": 2},
        {"tag": "Late Pickup", "count": 1},
        {"tag": "Polite", "count": 1},
    ]


def test_facet_summary_for_one_vehicle(client, ids):
    v1 = client.get("/api/reviews/summary", params={"vehicle_id": str(ids["v1"])}).json()
    assert (v1["total"], v1["overall_average"]) == (2, 4.5)
    none = client.get("/api/reviews/summary", params={"vehicle_id": str(ids["v3"])}).json()
    assert none["total"] == 0 and none["overall_average"] is None and none["top_tags"] == []
    assert all(r["count"] == 0 for r in none["rating_distribution"])


def test_list_newest_first_with_plates(client, ids):
    body = client.get("/api/reviews").json()
    assert body["total"] == 3
    assert [r["trip_id"] for r in body["items"]] == [str(ids["t2"]), str(ids["t4"]), str(ids["t1"])]
    assert body["items"][0]["license_plate"] == "RS90001"


def test_list_filters_and_paging(client, ids):
    assert client.get("/api/reviews", params={"rating": 5}).json()["total"] == 1
    page = client.get("/api/reviews", params={"page_size": 2}).json()
    assert len(page["items"]) == 2 and page["total"] == 3
    assert client.get("/api/reviews", params={"rating": 6}).status_code == 422
