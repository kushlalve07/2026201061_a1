from datetime import datetime, timedelta, timezone

# Dora: opening 50.00, then +25.00, -10.50, +5.25 (see tests/seed.py)
EXPECTED = [
    ("CREDIT", 50.00, 50.00),
    ("CREDIT", 25.00, 75.00),
    ("DEBIT", -10.50, 64.50),
    ("CREDIT", 5.25, 69.75),
]


def url(ids):
    return f"/api/riders/{ids['dora']}/wallet-audit"


def test_running_balance_matches_every_recorded_balance(client, ids):
    body = client.get(url(ids)).json()
    assert body["total"] == 4
    rows = [(r["action_type"], r["amount_changed"], r["running_balance"]) for r in body["items"]]
    assert rows == EXPECTED
    assert all(r["matches"] for r in body["items"])
    assert all(r["running_balance"] == r["balance_after"] for r in body["items"])


def test_summary(client, ids):
    body = client.get(url(ids)).json()
    assert body["summary"] == {
        "entries": 4,
        "opening_balance": 0.0,
        "credits_total": 80.25,
        "credits_count": 3,
        "debits_total": -10.50,
        "debits_count": 1,
        "closing_balance": 69.75,
    }
    assert body["rider"]["wallet_balance"] == 69.75


def test_descending_order_and_paging_keep_running_balance(client, ids):
    page2 = client.get(url(ids), params={"order": "desc", "page_size": 2, "page": 2}).json()
    assert [r["running_balance"] for r in page2["items"]] == [75.00, 50.00]
    assert page2["order"] == "desc"


def test_date_filter(client, ids):
    today = datetime.now(timezone.utc).date()
    same_day = client.get(url(ids), params={"from": today.isoformat(), "to": today.isoformat()}).json()
    assert same_day["total"] == 4
    future = client.get(url(ids), params={"from": (today + timedelta(days=1)).isoformat()}).json()
    assert future["total"] == 0
    assert future["items"] == []
    assert future["summary"]["opening_balance"] is None


def test_errors(client, ids):
    assert client.get("/api/riders/00000000-0000-0000-0000-000000000000/wallet-audit").status_code == 404
    assert client.get(url(ids), params={"order": "sideways"}).status_code == 422
    assert client.get(url(ids), params={"from": "not-a-date"}).status_code == 422
