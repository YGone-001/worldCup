from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "match_started",
    "goal",
    "shot",
    "red_card",
    "yellow_card",
    "substitution",
    "xg_update",
    "period_end",
    "match_finished",
]


class StandardEvent(BaseModel):
    event_id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    event_type: EventType
    event_time: datetime
    ingest_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    team_id: str | None = None
    player_id: str | None = None
    period: int = Field(default=1, ge=1, le=5)
    match_clock_sec: int = Field(default=0, ge=0, le=7800)
    x: float | None = Field(default=None, ge=0.0, le=100.0)
    y: float | None = Field(default=None, ge=0.0, le=100.0)
    source: str = Field(default="manual")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    correction_flag: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class TeamMatchState(BaseModel):
    score: int = 0
    red_cards: int = 0
    yellow_cards: int = 0
    shots: int = 0
    xg: float = 0.0


class MatchState(BaseModel):
    match_id: str
    home_team_id: str = "home"
    away_team_id: str = "away"
    status: str = "scheduled"
    period: int = 1
    match_clock_sec: int = 0
    home: TeamMatchState = Field(default_factory=TeamMatchState)
    away: TeamMatchState = Field(default_factory=TeamMatchState)
    last_event_id: str | None = None
    last_event_time: datetime | None = None
    degradation_level: int = 0


class WorldCupMatch(BaseModel):
    match_id: str
    match_no: int
    group: str
    stage: str
    kickoff_time_utc: datetime
    venue: str
    city: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    status: str
    home_score: int | None = None
    away_score: int | None = None
    source: str


class ModelContribution(BaseModel):
    model_name: str
    model_version: str
    weight: float = Field(ge=0.0, le=1.0)


class MatchPrediction(BaseModel):
    prediction_id: str
    prediction_version_id: str
    match_id: str
    generated_at: datetime
    feature_version: str
    models: list[ModelContribution]
    home_win: float = Field(ge=0.0, le=1.0)
    draw: float = Field(ge=0.0, le=1.0)
    away_win: float = Field(ge=0.0, le=1.0)
    expected_home_goals: float = Field(ge=0.0)
    expected_away_goals: float = Field(ge=0.0)
    expected_total_goals: float = Field(ge=0.0)
    over_2_5_goals: float = Field(ge=0.0, le=1.0)
    under_2_5_goals: float = Field(ge=0.0, le=1.0)
    confidence_level: float = Field(ge=0.0, le=1.0)
    degradation_level: int = Field(ge=0)


class PredictionEvaluation(BaseModel):
    match_id: str
    generated_at: datetime
    source_prediction_version_id: str | None = None
    status: str
    actual_home_goals: int | None = None
    actual_away_goals: int | None = None
    actual_total_goals: int | None = None
    predicted_home_goals: float | None = None
    predicted_away_goals: float | None = None
    predicted_total_goals: float | None = None
    total_goals_error: float | None = None
    actual_over_2_5_goals: bool | None = None
    predicted_over_2_5_goals: bool | None = None
    over_2_5_hit: bool | None = None
    outcome_brier_score: float | None = Field(default=None, ge=0.0)
    outcome_hit: bool | None = None
    note: str


class PredictionBacktestBucket(BaseModel):
    date: date
    match_count: int = Field(ge=0)
    settled_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    average_brier_score: float | None = Field(default=None, ge=0.0)
    total_goals_mae: float | None = Field(default=None, ge=0.0)
    over_2_5_hit_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class PredictionBacktestReport(BaseModel):
    generated_at: datetime
    date_from: date | None = None
    date_to: date | None = None
    match_count: int = Field(ge=0)
    settled_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    evaluated_count: int = Field(ge=0)
    average_brier_score: float | None = Field(default=None, ge=0.0)
    total_goals_mae: float | None = Field(default=None, ge=0.0)
    over_2_5_hit_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    buckets: list[PredictionBacktestBucket]
    evaluations: list[PredictionEvaluation]


class GoalCalibrationSnapshot(BaseModel):
    sample_count: int = Field(ge=0)
    total_goals_factor: float = Field(gt=0.0)
    total_goals_bias: float
    mean_absolute_error: float | None = Field(default=None, ge=0.0)
    last_match_id: str | None = None
    last_error: float | None = None
    updated_at: datetime | None = None


class LotteryOutcome(BaseModel):
    code: str
    label: str
    probability: float = Field(ge=0.0, le=1.0)
    fair_decimal_odds: float = Field(gt=0.0)


class LotteryAnalysis(BaseModel):
    match: WorldCupMatch
    generated_at: datetime
    source_prediction_version_id: str | None = None
    outcomes: list[LotteryOutcome]
    confidence_level: float = Field(ge=0.0, le=1.0)
    settlement_status: str
    note: str


class DataQualityResult(BaseModel):
    accepted: bool
    score: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    ingest_latency_ms: float = Field(ge=0.0)


class EventIngestResponse(BaseModel):
    accepted: bool
    event_id: str
    match_id: str
    data_quality: DataQualityResult
    prediction: MatchPrediction | None = None


class TeamSimulationResult(BaseModel):
    team_id: str
    group_advance_prob: float = Field(ge=0.0, le=1.0)
    quarter_final_prob: float = Field(ge=0.0, le=1.0)
    semi_final_prob: float = Field(ge=0.0, le=1.0)
    final_prob: float = Field(ge=0.0, le=1.0)
    champion_prob: float = Field(ge=0.0, le=1.0)


class SimulationResult(BaseModel):
    simulation_run_id: str
    generated_at: datetime
    runs: int
    teams: list[TeamSimulationResult]


class EventAuditRecord(BaseModel):
    event_id: str
    match_id: str
    event_type: str
    event_time: datetime
    received_at: datetime
    source: str
    accepted: bool
    score: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class RuntimeStatus(BaseModel):
    status: str
    event_count: int
    prediction_count: int
    bus_message_count: int
    active_ws_connections: int
