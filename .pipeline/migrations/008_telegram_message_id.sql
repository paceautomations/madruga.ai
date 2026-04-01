-- 008_telegram_message_id.sql — Add Telegram message ID tracking to pipeline_runs
-- Supports inline keyboard message editing after approve/reject (epic 014)

ALTER TABLE pipeline_runs ADD COLUMN telegram_message_id INTEGER;
