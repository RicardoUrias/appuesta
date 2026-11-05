CREATE TABLE IF NOT EXISTS provider_response_cache (
    cache_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_provider_response_cache_fetched_at
    ON provider_response_cache (fetched_at);
