--   psql -U ridesync -d ridesync -f sql/04_stored_procedures.sql
--
-- Call inside REPEATABLE READ:
--   BEGIN ISOLATION LEVEL REPEATABLE READ;
--   CALL sp_atomic_booking('<rider_id>', '<vehicle_id>', 250.00, NULL);
--   COMMIT;

CREATE OR REPLACE PROCEDURE sp_atomic_booking(
    IN    p_rider_id    UUID,
    IN    p_vehicle_id  UUID,
    IN    p_fare_amount DECIMAL(10, 2),
    INOUT p_trip_id     UUID DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_vehicle_active BOOLEAN;
BEGIN
    SELECT is_active
      INTO v_vehicle_active
      FROM vehicles
     WHERE id = p_vehicle_id;

    IF v_vehicle_active IS NULL THEN
        RAISE EXCEPTION 'vehicle % not found', p_vehicle_id;
    END IF;

    IF NOT v_vehicle_active THEN
        RAISE EXCEPTION 'vehicle % is not active', p_vehicle_id;
    END IF;

    UPDATE riders
       SET wallet_balance = wallet_balance - p_fare_amount
     WHERE id = p_rider_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'rider % not found', p_rider_id;
    END IF;

    INSERT INTO trips (rider_id, vehicle_id, fare_amount, status)
    VALUES (p_rider_id, p_vehicle_id, p_fare_amount, 'REQUESTED')
    RETURNING id INTO p_trip_id;

EXCEPTION
    WHEN check_violation THEN
        RAISE EXCEPTION
            'Atomic booking rolled back: CHECK constraint failed (insufficient wallet or invalid fare)'
            USING ERRCODE = 'check_violation';
    WHEN unique_violation THEN
        RAISE EXCEPTION
            'Atomic booking rolled back: rider already has an active trip'
            USING ERRCODE = 'unique_violation';
END;
$$;
