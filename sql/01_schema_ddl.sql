-- RideSync (Project 2) — PostgreSQL schema
-- Step 1: tables, types, PKs/FKs, CHECK constraints
--
-- Apply after creating the database (see README.md):
--   psql -U ridesync -d ridesync -f sql/01_schema_ddl.sql
--
-- Requires PostgreSQL 13+ (gen_random_uuid() is built-in; no uuid-ossp).

CREATE TABLE riders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    wallet_balance  DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT riders_wallet_balance_nonnegative
        CHECK (wallet_balance >= 0.00)
);

CREATE TABLE vehicles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_plate   VARCHAR(20) NOT NULL,
    class           VARCHAR(30) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT vehicles_license_plate_unique UNIQUE (license_plate)
);

CREATE TABLE trips (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rider_id        UUID NOT NULL,
    vehicle_id      UUID NOT NULL,
    fare_amount     DECIMAL(10, 2) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT trips_rider_id_fkey
        FOREIGN KEY (rider_id) REFERENCES riders (id),
    CONSTRAINT trips_vehicle_id_fkey
        FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
    CONSTRAINT trips_fare_amount_nonnegative
        CHECK (fare_amount >= 0.00),
    CONSTRAINT trips_status_allowed
        CHECK (status IN ('REQUESTED', 'IN_TRANSIT', 'COMPLETED'))
);

CREATE TABLE wallet_audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rider_id        UUID NOT NULL,
    amount_changed  DECIMAL(10, 2) NOT NULL,
    action_type     VARCHAR(10) NOT NULL,
    balance_after   DECIMAL(10, 2) NOT NULL,
    "timestamp"     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT wallet_audit_logs_rider_id_fkey
        FOREIGN KEY (rider_id) REFERENCES riders (id),
    CONSTRAINT wallet_audit_logs_action_type_allowed
        CHECK (action_type IN ('DEBIT', 'CREDIT'))
);

COMMENT ON TABLE riders IS 'Riders and prepaid wallet. wallet_balance cannot go below 0.00.';
COMMENT ON TABLE vehicles IS 'Fleet vehicles that can be assigned to trips.';
COMMENT ON TABLE trips IS 'A ride booking. Status uses IN_TRANSIT (underscore), not a space.';
COMMENT ON TABLE wallet_audit_logs IS 'Immutable wallet history. Rows are inserted by a trigger in Step 2.';
