CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE riders (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    wallet_balance  DECIMAL(10,2) NOT NULL DEFAULT 0.00
                    CHECK (wallet_balance >= 0.00)
);

CREATE TABLE vehicles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    license_plate   VARCHAR(20) NOT NULL UNIQUE,
    class           VARCHAR(30) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE trips (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rider_id        UUID NOT NULL REFERENCES riders(id),
    vehicle_id      UUID NOT NULL REFERENCES vehicles(id),
    fare_amount     DECIMAL(10,2) NOT NULL CHECK (fare_amount >= 0.00),
    status          VARCHAR(20) NOT NULL
                    CHECK (status IN ('REQUESTED', 'IN_TRANSIT', 'COMPLETED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE wallet_audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rider_id        UUID NOT NULL REFERENCES riders(id),
    amount_changed  DECIMAL(10,2) NOT NULL,
    action_type     VARCHAR(10) NOT NULL CHECK (action_type IN ('DEBIT', 'CREDIT')),
    balance_after   DECIMAL(10,2) NOT NULL,
    "timestamp"     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);