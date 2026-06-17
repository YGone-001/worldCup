CREATE TABLE IF NOT EXISTS match_event_ts
(
    event_time DateTime64(3),
    ingest_time DateTime64(3),
    match_id String,
    event_id String,
    event_type String,
    team_id String,
    player_id String,
    x Float32,
    y Float32,
    source String,
    confidence_score Float32
)
ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (match_id, event_time, event_id);

CREATE TABLE IF NOT EXISTS prediction_ts
(
    prediction_time DateTime64(3),
    match_id String,
    prediction_version_id String,
    model_name String,
    model_version String,
    home_win_prob Float32,
    draw_prob Float32,
    away_win_prob Float32,
    confidence_level Float32
)
ENGINE = MergeTree
PARTITION BY toDate(prediction_time)
ORDER BY (match_id, prediction_time, prediction_version_id);

