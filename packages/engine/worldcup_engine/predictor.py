from datetime import UTC, datetime
from dataclasses import dataclass
from math import exp
from uuid import uuid4

from packages.domain.worldcup_domain.schemas import (
    GoalCalibrationSnapshot,
    MatchPrediction,
    MatchState,
)
from packages.engine.worldcup_engine.aggregator import PredictionAggregator


@dataclass
class GoalProjectionCalibrator:
    sample_count: int = 0
    total_goals_factor: float = 1.0
    total_goals_bias: float = 0.0
    mean_absolute_error: float | None = None
    last_match_id: str | None = None
    last_error: float | None = None
    updated_at: datetime | None = None
    learning_rate: float = 0.18

    def apply(self, home_goals: float, away_goals: float) -> tuple[float, float]:
        raw_total = max(0.01, home_goals + away_goals)
        calibrated_total = max(0.01, raw_total * self.total_goals_factor + self.total_goals_bias)
        ratio = calibrated_total / raw_total
        return home_goals * ratio, away_goals * ratio

    def update(
        self,
        match_id: str,
        predicted_total_goals: float,
        actual_total_goals: int,
    ) -> GoalCalibrationSnapshot:
        safe_prediction = max(0.2, predicted_total_goals)
        error = float(actual_total_goals) - predicted_total_goals
        target_factor = max(0.72, min(1.32, float(actual_total_goals) / safe_prediction))

        self.total_goals_factor = (
            self.total_goals_factor * (1.0 - self.learning_rate)
            + target_factor * self.learning_rate
        )
        self.total_goals_factor = max(0.72, min(1.32, self.total_goals_factor))
        self.total_goals_bias = (
            self.total_goals_bias * (1.0 - self.learning_rate)
            + error * self.learning_rate * 0.18
        )
        self.total_goals_bias = max(-0.35, min(0.35, self.total_goals_bias))

        absolute_error = abs(error)
        if self.mean_absolute_error is None:
            self.mean_absolute_error = absolute_error
        else:
            self.mean_absolute_error = (
                self.mean_absolute_error * (1.0 - self.learning_rate)
                + absolute_error * self.learning_rate
            )
        self.sample_count += 1
        self.last_match_id = match_id
        self.last_error = round(error, 4)
        self.updated_at = datetime.now(UTC)
        return self.snapshot()

    def snapshot(self) -> GoalCalibrationSnapshot:
        return GoalCalibrationSnapshot(
            sample_count=self.sample_count,
            total_goals_factor=round(self.total_goals_factor, 4),
            total_goals_bias=round(self.total_goals_bias, 4),
            mean_absolute_error=(
                round(self.mean_absolute_error, 4)
                if self.mean_absolute_error is not None
                else None
            ),
            last_match_id=self.last_match_id,
            last_error=self.last_error,
            updated_at=self.updated_at,
        )


class BaselinePredictionEngine:
    def __init__(
        self,
        aggregator: PredictionAggregator,
        goal_calibrator: GoalProjectionCalibrator | None = None,
    ) -> None:
        self.aggregator = aggregator
        self.goal_calibrator = goal_calibrator or GoalProjectionCalibrator()

    def predict(self, state: MatchState) -> MatchPrediction:
        if state.status == "finished":
            return self._settled_prediction(state)

        remaining_ratio = max(0.0, min(1.0, (5400 - state.match_clock_sec) / 5400))
        score_delta = state.home.score - state.away.score
        xg_delta = state.home.xg - state.away.xg
        shot_delta = (state.home.shots - state.away.shots) * 0.035
        red_card_delta = (state.away.red_cards - state.home.red_cards) * 0.35

        live_strength = score_delta * (1.0 - 0.35 * remaining_ratio)
        live_strength += xg_delta * 0.42
        live_strength += shot_delta
        live_strength += red_card_delta

        home_raw = self._sigmoid(0.15 + live_strength)
        away_raw = self._sigmoid(-0.15 - live_strength)
        draw_raw = max(0.08, 0.36 * remaining_ratio + 0.16 * (1.0 - abs(score_delta) / 3.0))

        home_win, draw, away_win = self.aggregator.normalize(home_raw, draw_raw, away_raw)
        event_signal = min(0.24, (state.home.shots + state.away.shots) * 0.015)
        expected_home_goals, expected_away_goals = self._project_goals(state)
        expected_home_goals, expected_away_goals = self.goal_calibrator.apply(
            expected_home_goals,
            expected_away_goals,
        )
        expected_total_goals = expected_home_goals + expected_away_goals
        over_2_5_goals = self._over_probability(expected_total_goals, line=2.5)

        prediction_version = f"pv_{uuid4().hex}"
        generated_at = datetime.now(UTC)
        return MatchPrediction(
            prediction_id=f"pred_{uuid4().hex}",
            prediction_version_id=prediction_version,
            match_id=state.match_id,
            generated_at=generated_at,
            feature_version=f"fv_{state.match_id}_{state.last_event_id or 'initial'}",
            models=self.aggregator.default_models(),
            home_win=round(home_win, 4),
            draw=round(draw, 4),
            away_win=round(away_win, 4),
            expected_home_goals=round(expected_home_goals, 3),
            expected_away_goals=round(expected_away_goals, 3),
            expected_total_goals=round(expected_total_goals, 3),
            over_2_5_goals=round(over_2_5_goals, 4),
            under_2_5_goals=round(1.0 - over_2_5_goals, 4),
            confidence_level=self.aggregator.confidence(event_signal, state.degradation_level),
            degradation_level=state.degradation_level,
        )

    def _sigmoid(self, value: float) -> float:
        return 1.0 / (1.0 + exp(-value))

    def calibrate_total_goals(
        self,
        match_id: str,
        predicted_total_goals: float,
        actual_total_goals: int,
    ) -> GoalCalibrationSnapshot:
        return self.goal_calibrator.update(
            match_id=match_id,
            predicted_total_goals=predicted_total_goals,
            actual_total_goals=actual_total_goals,
        )

    def calibration_snapshot(self) -> GoalCalibrationSnapshot:
        return self.goal_calibrator.snapshot()

    def _project_goals(self, state: MatchState) -> tuple[float, float]:
        remaining_ratio = max(0.0, min(1.0, (5400 - state.match_clock_sec) / 5400))
        elapsed_ratio = max(0.08, 1.0 - remaining_ratio)

        home_attack = max(state.home.xg, state.home.shots * 0.085)
        away_attack = max(state.away.xg, state.away.shots * 0.085)
        home_advantage = 0.12
        red_card_swing = (state.away.red_cards - state.home.red_cards) * 0.18

        home_future_rate = 1.16 + home_advantage + home_attack * 0.22 + red_card_swing
        away_future_rate = 1.04 + away_attack * 0.22 - red_card_swing

        home_pace_bonus = max(0.0, home_attack / elapsed_ratio - 1.16) * 0.18
        away_pace_bonus = max(0.0, away_attack / elapsed_ratio - 1.04) * 0.18

        home_expected = state.home.score + remaining_ratio * max(
            0.05,
            home_future_rate + home_pace_bonus,
        )
        away_expected = state.away.score + remaining_ratio * max(
            0.05,
            away_future_rate + away_pace_bonus,
        )
        return home_expected, away_expected

    def _over_probability(self, expected_total_goals: float, line: float) -> float:
        if line != 2.5:
            raise ValueError("Only 2.5 goal line is supported by the baseline model.")

        lambda_goals = max(0.01, expected_total_goals)
        under_or_equal_two = exp(-lambda_goals) * (
            1.0 + lambda_goals + (lambda_goals**2) / 2.0
        )
        return max(0.0, min(1.0, 1.0 - under_or_equal_two))

    def _settled_prediction(self, state: MatchState) -> MatchPrediction:
        if state.home.score > state.away.score:
            home_win, draw, away_win = 1.0, 0.0, 0.0
        elif state.home.score == state.away.score:
            home_win, draw, away_win = 0.0, 1.0, 0.0
        else:
            home_win, draw, away_win = 0.0, 0.0, 1.0

        expected_total_goals = float(state.home.score + state.away.score)
        over_2_5_goals = 1.0 if expected_total_goals > 2.5 else 0.0
        prediction_version = f"pv_{uuid4().hex}"
        generated_at = datetime.now(UTC)
        return MatchPrediction(
            prediction_id=f"pred_{uuid4().hex}",
            prediction_version_id=prediction_version,
            match_id=state.match_id,
            generated_at=generated_at,
            feature_version=f"fv_{state.match_id}_{state.last_event_id or 'settled'}",
            models=self.aggregator.default_models(),
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            expected_home_goals=float(state.home.score),
            expected_away_goals=float(state.away.score),
            expected_total_goals=expected_total_goals,
            over_2_5_goals=over_2_5_goals,
            under_2_5_goals=1.0 - over_2_5_goals,
            confidence_level=1.0,
            degradation_level=state.degradation_level,
        )
