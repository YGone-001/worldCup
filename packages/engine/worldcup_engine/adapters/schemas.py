from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ScheduleStatus = Literal[
    "scheduled",
    "live",
    "finished",
    "postponed",
    "suspended",
    "cancelled",
]
OddsMarket = Literal["win_draw_win", "handicap_win_draw_win"]
OddsOutcome = Literal["home_win", "draw", "away_win"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExternalScheduleUpdate(StrictModel):
    event_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    external_match_id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    status: ScheduleStatus
    kickoff_time_utc: datetime | None = None
    home_score: int | None = Field(default=None, ge=0)
    away_score: int | None = Field(default=None, ge=0)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_finished_score(self) -> ExternalScheduleUpdate:
        if self.status == "finished" and (self.home_score is None or self.away_score is None):
            raise ValueError("finished_match_requires_score")
        return self


class OddsSelection(StrictModel):
    outcome: OddsOutcome
    decimal_odds: float = Field(gt=1.0)
    water_level: float | None = Field(default=None, gt=0.0)


class ExternalOddsUpdate(StrictModel):
    event_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    external_match_id: str = Field(min_length=1)
    match_id: str = Field(min_length=1)
    lottery_match_no: str | None = Field(default=None, min_length=1)
    market: OddsMarket
    handicap: float | None = None
    selections: list[OddsSelection] = Field(min_length=3, max_length=3)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str | None = Field(default=None, min_length=1)
    source_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("selections")
    @classmethod
    def validate_unique_outcomes(cls, selections: list[OddsSelection]) -> list[OddsSelection]:
        outcomes = {selection.outcome for selection in selections}
        if outcomes != {"home_win", "draw", "away_win"}:
            raise ValueError("odds_update_requires_home_draw_away")
        return selections

    @model_validator(mode="after")
    def validate_market_handicap(self) -> ExternalOddsUpdate:
        if self.market == "handicap_win_draw_win" and self.handicap is None:
            raise ValueError("handicap_market_requires_handicap")
        return self
