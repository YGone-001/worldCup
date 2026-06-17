CREATE TABLE IF NOT EXISTS teams (
    team_id VARCHAR(64) PRIMARY KEY,
    team_name VARCHAR(128) NOT NULL,
    confederation VARCHAR(32),
    fifa_rank INTEGER,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    match_id VARCHAR(64) PRIMARY KEY,
    competition_id VARCHAR(64) NOT NULL,
    stage VARCHAR(64) NOT NULL,
    home_team_id VARCHAR(64) NOT NULL,
    away_team_id VARCHAR(64) NOT NULL,
    venue_id VARCHAR(64),
    kickoff_time_utc TIMESTAMP NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version_id VARCHAR(128) PRIMARY KEY,
    model_name VARCHAR(128) NOT NULL,
    version VARCHAR(64) NOT NULL,
    artifact_uri VARCHAR(512) NOT NULL,
    status VARCHAR(32) NOT NULL,
    metrics_json JSONB,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS prediction_versions (
    prediction_version_id VARCHAR(128) PRIMARY KEY,
    match_id VARCHAR(64) NOT NULL,
    model_version_id VARCHAR(128),
    feature_version VARCHAR(128) NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    status VARCHAR(32) NOT NULL
);

