CREATE UNIQUE INDEX idx_active_rider_trip
    ON trips (rider_id)
    WHERE status IN ('REQUESTED', 'IN_TRANSIT');

CREATE INDEX idx_trips_completed_vehicle_date
    ON trips (vehicle_id, created_at)
    INCLUDE (fare_amount)
    WHERE status = 'COMPLETED';

CREATE INDEX idx_trips_vehicle_id ON trips (vehicle_id);
CREATE INDEX idx_trips_rider_id   ON trips (rider_id);

CREATE INDEX idx_wallet_audit_logs_rider_time
    ON wallet_audit_logs (rider_id, "timestamp" DESC);