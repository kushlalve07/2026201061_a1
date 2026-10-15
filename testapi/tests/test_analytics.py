def test_fleet_summary_matches_the_trips_table_after_refresh(client, db):
    refreshed = client.post("/api/analytics/fleet-summary/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["duration_ms"] >= 0

    body = client.get("/api/analytics/fleet-summary").json()
    trips, earnings = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(fare_amount), 0) FROM trips WHERE status = 'COMPLETED'"
    ).fetchone()
    vehicles, active = db.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE is_active) FROM vehicles").fetchone()
    assert body["lifetime_trips"] == trips
    assert body["total_earnings"] == float(earnings)
    assert (body["total_vehicles"], body["active_vehicles"]) == (vehicles, active)
    assert body["last_refreshed_at"] == refreshed.json()["refreshed_at"]
    assert [v["license_plate"] for v in body["top_vehicles"][:2]] == ["RS90001", "RS90002"]


def test_refresh_moves_last_refreshed_forward(client):
    first = client.post("/api/analytics/fleet-summary/refresh").json()["refreshed_at"]
    second = client.post("/api/analytics/fleet-summary/refresh").json()["refreshed_at"]
    assert second > first


def test_ranking_uses_dense_rank(client, ids):
    items = client.get("/api/analytics/revenue-ranking", params={"page_size": 100}).json()["items"]
    rank = {i["license_plate"]: i["revenue_rank"] for i in items}
    assert rank["RS90001"] == rank["RS90002"] == 1  # tie at 180.00
    assert rank["RS90004"] == 2                     # dense: no gap after the tie
    assert "RS90003" not in rank                    # no completed trips


def test_trend_reproduces_part_a_window(client, ids):
    body = client.get(f"/api/analytics/vehicles/{ids['v1']}/revenue-trend", params={"days": 8}).json()
    assert (body["date_from"], body["date_to"]) == ("2026-06-01", "2026-06-08")
    assert body["revenue_rank"] == 1 and body["total_revenue"] == 180.00
    points = [(p["day"], p["daily_total"], p["moving_avg_7day"]) for p in body["points"]]
    # Part A: the window only sees days that had trips -> 06-08 averages 06-03 and 06-08
    assert points == [("2026-06-01", 100.0, 100.0), ("2026-06-03", 50.0, 75.0), ("2026-06-08", 30.0, 40.0)]


def test_trend_zero_fill_uses_calendar_days(client, ids):
    body = client.get(
        f"/api/analytics/vehicles/{ids['v1']}/revenue-trend", params={"days": 8, "zero_fill": True}
    ).json()
    points = {p["day"]: p for p in body["points"]}
    assert len(points) == 8
    assert points["2026-06-02"]["daily_total"] == 0 and points["2026-06-02"]["has_trips"] is False
    assert points["2026-06-01"]["moving_avg_7day"] == 14.29  # 100 / 7
    assert points["2026-06-03"]["moving_avg_7day"] == 21.43  # 150 / 7
    assert points["2026-06-08"]["moving_avg_7day"] == 11.43  # (50 + 30) / 7


def test_trend_for_vehicle_without_trips_and_errors(client, ids):
    body = client.get(f"/api/analytics/vehicles/{ids['v3']}/revenue-trend").json()
    assert body["points"] == [] and body["revenue_rank"] is None
    assert client.get("/api/analytics/vehicles/00000000-0000-0000-0000-000000000000/revenue-trend").status_code == 404
    assert client.get(f"/api/analytics/vehicles/{ids['v1']}/revenue-trend", params={"days": 3}).status_code == 422
