-- RideSync (Project 2)
-- Step 3 : Triggers and Audit Logs

CREATE OR REPLACE FUNCTION auditlog()
RETURNS TRIGGER AS $$
    BEGIN
        INSERT INTO wallet_audit_logs(rider_id, amount_changed, action_type, balance_after, "timestamp")
        VALUES (
            NEW.id, 
            NEW.wallet_balance - OLD.wallet_balance, 
            CASE
                WHEN NEW.wallet_balance > OLD.wallet_balance THEN 'CREDIT'
                ELSE 'DEBIT'
            END,
            NEW.wallet_balance,
            NOW()
        );
        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rider_wallet_audit
AFTER UPDATE OF wallet_balance on riders
FOR EACH ROW
WHEN (OLD.wallet_balance IS DISTINCT FROM NEW.wallet_balance)
EXECUTE FUNCTION auditlog();