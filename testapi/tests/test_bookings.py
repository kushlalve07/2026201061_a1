"""Workflow 1 through the API. Every test books on RS90005 (v5) with its own fresh rider."""
from datetime import datetime


def book(client, rider_id, vehicle_id, fare):
    return client.post(
        "/api/bookings", json={"rider_id": str(rider_id), "vehicle_id": str(vehicle_id), "fare_amount": fare}
    )


def audit_rows(db, rider_id):
    return db.execute("SELECT COUNT(*) FROM wallet_audit_logs WHERE rider_id = %s", (rider_id,)).fetchone()[0]


def test_success_shows_balances_trip_and_trigger_row(client, ids, new_rider):
    rider = new_rider(100.00)
    res = book(client, rider, ids["v5"], "24.50")
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "COMMITTED"
    assert body["reason"] is None
    assert body["message"] == "COMMITTED"
    assert (body["balance_before"], body["balance_after"]) == (100.00, 75.50)
    assert body["trip"]["status"] == "REQUESTED"
    assert body["trip"]["vehicle"]["license_plate"] == "RS90005"
    audit = body["audit_entry"]
    assert audit["action_type"] == "DEBIT"
    assert audit["amount_changed"] == -24.50
    assert audit["balance_after"] == 75.50
    # same transaction -> same NOW() for the trip and its audit row
    assert datetime.fromisoformat(audit["timestamp"]) == datetime.fromisoformat(body["trip"]["created_at"])


def test_fare_is_rounded_once_for_trip_and_wallet(client, ids, new_rider):
    rider = new_rider(100.00)
    body = book(client, rider, ids["v5"], "10.005").json()
    assert body["fare_amount"] == 10.01
    assert body["trip"]["fare_amount"] == 10.01
    assert body["audit_entry"]["amount_changed"] == -10.01
    assert body["balance_after"] == 89.99


def test_second_active_trip_is_blocked_by_partial_unique_index(client, ids, new_rider, db):
    rider = new_rider(100.00)
    first = book(client, rider, ids["v5"], 10).json()
    before = audit_rows(db, rider)
    res = book(client, rider, ids["v5"], 10)
    assert res.status_code == 409
    body = res.json()
    assert body["reason"] == "ACTIVE_TRIP_EXISTS"
    assert body["message"] == "ROLLED_BACK: rider already has an active trip"
    assert body["active_trip_id"] == first["trip"]["id"]
    assert body["balance_before"] == body["balance_after"] == 90.00
    assert audit_rows(db, rider) == before


def test_insufficient_balance_rolls_back(client, ids, new_rider, db):
    rider = new_rider(5.00)
    res = book(client, rider, ids["v5"], 50)
    assert res.status_code == 409
    body = res.json()
    assert body["reason"] == "INSUFFICIENT_BALANCE"
    assert body["balance_before"] == body["balance_after"] == 5.00
    assert body["trip"] is None and body["audit_entry"] is None
    assert db.execute("SELECT COUNT(*) FROM trips WHERE rider_id = %s", (rider,)).fetchone()[0] == 0


def test_zero_and_negative_fares_are_rejected(client, ids, new_rider, db):
    rider = new_rider(100.00)
    for fare in (0, "-5.00"):
        res = book(client, rider, ids["v5"], fare)
        assert res.status_code == 400
        assert res.json()["reason"] == "INVALID_FARE"
        assert res.json()["balance_after"] == 100.00
    assert audit_rows(db, rider) == 1  # opening balance only


def test_inactive_vehicle(client, ids, new_rider):
    res = book(client, new_rider(100.00), ids["v3"], 10)
    assert res.status_code == 409
    assert res.json()["reason"] == "VEHICLE_INACTIVE"


def test_unknown_rider_or_vehicle(client, ids, new_rider):
    res = book(client, "00000000-0000-0000-0000-000000000000", ids["v5"], 10)
    assert res.status_code == 404
    assert res.json()["reason"] == "NOT_FOUND"
    assert res.json()["balance_before"] is None
    res = book(client, new_rider(100.00), "00000000-0000-0000-0000-000000000000", 10)
    assert res.status_code == 404


def test_malformed_requests(client, ids, new_rider):
    rider = new_rider(100.00)
    for payload in (
        {"rider_id": str(rider), "vehicle_id": str(ids["v5"]), "fare_amount": "abc"},
        {"vehicle_id": str(ids["v5"]), "fare_amount": 10},
        {"rider_id": str(rider), "vehicle_id": str(ids["v5"]), "fare_amount": "100000000"},
    ):
        res = client.post("/api/bookings", json=payload)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_full_journey_blocked_then_allowed(client, ids, new_rider):
    rider = new_rider(100.00)
    trip_id = book(client, rider, ids["v5"], 5).json()["trip"]["id"]
    assert book(client, rider, ids["v5"], 5).status_code == 409
    assert client.patch(f"/api/trips/{trip_id}/status", json={"status": "IN_TRANSIT"}).status_code == 200
    assert book(client, rider, ids["v5"], 5).status_code == 409  # IN_TRANSIT is still active
    assert client.patch(f"/api/trips/{trip_id}/status", json={"status": "COMPLETED"}).status_code == 200
    again = book(client, rider, ids["v5"], 5)
    assert again.status_code == 201
    assert again.json()["balance_after"] == 90.00
