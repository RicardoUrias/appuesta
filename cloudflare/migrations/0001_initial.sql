CREATE TABLE IF NOT EXISTS team_directory_cache (
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    teams_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (league_id, season)
) STRICT;

CREATE TABLE IF NOT EXISTS team_stats_cache (
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    stats_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (league_id, season, team_id)
) STRICT;

CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    stats_season INTEGER NOT NULL,
    odds_region TEXT NOT NULL,
    events_seen INTEGER NOT NULL DEFAULT 0,
    picks_saved INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE IF NOT EXISTS picks (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    kickoff TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    market_key TEXT NOT NULL CHECK (market_key IN ('h2h', 'totals')),
    outcome_key TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL NOT NULL DEFAULT -1,
    bookmaker TEXT NOT NULL,
    odds REAL NOT NULL CHECK (odds > 1),
    model_probability REAL NOT NULL CHECK (model_probability >= 0 AND model_probability <= 1),
    implied_probability REAL NOT NULL CHECK (implied_probability >= 0 AND implied_probability <= 1),
    push_probability REAL NOT NULL DEFAULT 0 CHECK (push_probability >= 0 AND push_probability <= 1),
    edge REAL NOT NULL,
    expected_value REAL NOT NULL,
    stats_season INTEGER NOT NULL,
    odds_region TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'won', 'lost', 'push', 'void')),
    final_home_score INTEGER,
    final_away_score INTEGER,
    created_at TEXT NOT NULL,
    settled_at TEXT,
    run_id TEXT NOT NULL REFERENCES analysis_runs(id),
    UNIQUE (event_id, market_key, outcome_key, line)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_picks_status_kickoff
    ON picks (status, kickoff);

CREATE INDEX IF NOT EXISTS idx_picks_created_at
    ON picks (created_at DESC);
