CREATE OR REPLACE PROCEDURE sp_atomic_booking(
    IN    p_rider_id    UUID,
    IN    p_vehicle_id  UUID,
    IN    p_fare_amount DECIMAL(10, 2),
    INOUT p_trip_id     UUID DEFAULT NULL,
    INOUT p_status      TEXT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_vehicle_active BOOLEAN;
BEGIN
    COMMIT;
    SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

    BEGIN
        SELECT is_active INTO v_vehicle_active
          FROM vehicles WHERE id = p_vehicle_id FOR SHARE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'vehicle % not found', p_vehicle_id
                USING ERRCODE = 'no_data_found';
        END IF;

        IF NOT v_vehicle_active THEN
            RAISE EXCEPTION 'vehicle % is not active', p_vehicle_id
                USING ERRCODE = 'no_data_found';
        END IF;

        UPDATE riders
           SET wallet_balance = wallet_balance - p_fare_amount
         WHERE id = p_rider_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'rider % not found', p_rider_id
                USING ERRCODE = 'no_data_found';
        END IF;

        INSERT INTO trips (rider_id, vehicle_id, fare_amount, status)
        VALUES (p_rider_id, p_vehicle_id, p_fare_amount, 'REQUESTED')
        RETURNING id INTO p_trip_id;

        p_status := 'COMMITTED';

    EXCEPTION
        WHEN check_violation THEN
            p_status := 'ROLLED_BACK: insufficient wallet balance';
            p_trip_id := NULL;
        WHEN unique_violation THEN
            p_status := 'ROLLED_BACK: rider already has an active trip';
            p_trip_id := NULL;
        WHEN no_data_found THEN
            p_status := 'ROLLED_BACK: ' || SQLERRM;
            p_trip_id := NULL;
        WHEN serialization_failure THEN
            p_status := 'ROLLED_BACK: concurrent update, retry';
            p_trip_id := NULL;
    END;

    IF p_status = 'COMMITTED' THEN
        COMMIT;
    ELSE
        ROLLBACK;
    END IF;
END;
$$;