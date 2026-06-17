from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
import os

from fastapi import WebSocket

from packages.domain.worldcup_domain.schemas import (
    DataQualityResult,
    EventAuditRecord,
    GoalCalibrationSnapshot,
    LotteryAnalysis,
    MatchPrediction,
    MatchState,
    PredictionBacktestBucket,
    PredictionBacktestReport,
    PredictionEvaluation,
    RuntimeStatus,
    SimulationResult,
    StandardEvent,
    WorldCupMatch,
)
from packages.engine.worldcup_engine.aggregator import PredictionAggregator
from packages.engine.worldcup_engine.consumer_worker import KafkaPredictionConsumerWorker
from packages.engine.worldcup_engine.adapters.external_fetcher import (
    ExternalFetcherConfig,
    ExternalFetcherService,
)
from packages.engine.worldcup_engine.adapters.schemas import (
    ExternalOddsUpdate,
    ExternalScheduleUpdate,
)
from packages.engine.worldcup_engine.adapters.store import ExternalDataStore
from packages.engine.worldcup_engine.event_bus import (
    JsonlEventBus,
    NORMALIZED_MATCH_EVENTS_TOPIC,
    PREDICTIONS_LIVE_TOPIC,
)
from packages.engine.worldcup_engine.event_bus_kafka import (
    KafkaEventBus,
    PREDICTIONS_UPDATED_TOPIC,
    RAW_EVENTS_TOPIC,
)
from packages.engine.worldcup_engine.predictor import BaselinePredictionEngine
from packages.engine.worldcup_engine.quality import DataQualityService
from packages.engine.worldcup_engine.simulation import TournamentSimulator
from packages.engine.worldcup_engine.storage import InMemoryPredictionStore
from packages.engine.worldcup_engine.worldcup_progress import WorldCupProgressProvider


class Runtime:
    def __init__(self) -> None:
        self.store = InMemoryPredictionStore()
        self.event_bus_mode = os.getenv("WORLDCUP_EVENT_BUS", "jsonl").lower()
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
        self.kafka_raw_topic = os.getenv("WORLDCUP_KAFKA_RAW_TOPIC", RAW_EVENTS_TOPIC)
        self.kafka_prediction_topic = os.getenv(
            "WORLDCUP_KAFKA_PREDICTION_TOPIC",
            PREDICTIONS_UPDATED_TOPIC,
        )
        self.kafka_consumer_group = os.getenv(
            "WORLDCUP_KAFKA_CONSUMER_GROUP",
            "worldcup-prediction-engine",
        )
        self.external_fetcher_enabled = os.getenv(
            "WORLDCUP_EXTERNAL_FETCHER_ENABLED",
            "true",
        ).lower() in {"1", "true", "yes", "on"}
        if self.event_bus_mode == "kafka":
            self.event_bus = KafkaEventBus(self.kafka_bootstrap_servers)
        else:
            self.event_bus = JsonlEventBus(Path("data/events"))
        self.quality = DataQualityService()
        self.engine = BaselinePredictionEngine(PredictionAggregator())
        self.simulator = TournamentSimulator()
        self.worldcup = WorldCupProgressProvider()
        self.event_audit: list[EventAuditRecord] = []
        self.clients: dict[WebSocket, set[str]] = {}
        self.consumer_worker: KafkaPredictionConsumerWorker | None = None
        self.external_store = ExternalDataStore()
        self.external_fetcher: ExternalFetcherService | None = None

    async def startup(self) -> None:
        if self.event_bus_mode == "kafka":
            assert isinstance(self.event_bus, KafkaEventBus)
            await self.event_bus.connect()
            self.consumer_worker = KafkaPredictionConsumerWorker(
                bootstrap_servers=self.kafka_bootstrap_servers,
                group_id=self.kafka_consumer_group,
                store=self.store,
                quality=self.quality,
                engine=self.engine,
                worldcup=self.worldcup,
                prediction_bus=self.event_bus,
                event_audit=self.event_audit,
                raw_topic=self.kafka_raw_topic,
                prediction_topic=self.kafka_prediction_topic,
                on_prediction=self.broadcast_prediction,
            )
            await self.consumer_worker.start()

        if self.external_fetcher_enabled:
            self.external_fetcher = ExternalFetcherService(
                config=ExternalFetcherConfig.from_env(),
                publisher=self.event_bus,
                store=self.external_store,
            )
            await self.external_fetcher.start()
            await self.refresh_external_data()

    async def shutdown(self) -> None:
        if self.external_fetcher is not None:
            await self.external_fetcher.stop()
            self.external_fetcher = None

        if self.consumer_worker is not None:
            await self.consumer_worker.stop()
            self.consumer_worker = None

        if isinstance(self.event_bus, KafkaEventBus):
            await self.event_bus.disconnect()

    async def ingest_event(
        self,
        event: StandardEvent,
    ) -> tuple[MatchPrediction | None, DataQualityResult]:
        if self.event_bus_mode == "kafka":
            return await self._ingest_event_kafka(event)

        return self._ingest_event_local(event)

    async def _ingest_event_kafka(
        self,
        event: StandardEvent,
    ) -> tuple[MatchPrediction | None, DataQualityResult]:
        quality = self.quality.inspect(event, duplicate=self.store.has_event(event.event_id))

        if quality.accepted:
            assert isinstance(self.event_bus, KafkaEventBus)
            await self.event_bus.publish_event(self.kafka_raw_topic, event)

        return self.store.get_prediction(event.match_id), quality

    def _ingest_event_local(
        self,
        event: StandardEvent,
    ) -> tuple[MatchPrediction, DataQualityResult]:
        quality = self.quality.inspect(event, duplicate=self.store.has_event(event.event_id))
        self.event_audit.append(
            EventAuditRecord(
                event_id=event.event_id,
                match_id=event.match_id,
                event_type=event.event_type,
                event_time=event.event_time,
                received_at=datetime.now(UTC),
                source=event.source,
                accepted=quality.accepted,
                score=quality.score,
                warnings=quality.warnings,
            )
        )

        if quality.accepted:
            self.event_bus.publish_event(NORMALIZED_MATCH_EVENTS_TOPIC, event)

        previous_prediction = self.store.get_prediction(event.match_id)
        state = self.store.apply_event(event)

        if quality.accepted and previous_prediction is not None:
            self._calibrate_goal_projection(event, state, previous_prediction)

        prediction = self.engine.predict(state)

        if quality.accepted:
            self.store.save_prediction(prediction)
            self.event_bus.publish_prediction(PREDICTIONS_LIVE_TOPIC, prediction)
        else:
            prediction = self.store.get_prediction(event.match_id) or prediction

        return prediction, quality

    def get_prediction(self, match_id: str) -> MatchPrediction | None:
        return self.store.get_prediction(match_id)

    def get_goal_calibration(self) -> GoalCalibrationSnapshot:
        return self.engine.calibration_snapshot()

    def list_worldcup_matches(self) -> list[WorldCupMatch]:
        schedule_by_match_id = {
            update.match_id: update for update in self.external_store.list_schedule_updates()
        }
        matches: list[WorldCupMatch] = []
        for match in self.worldcup.list_matches():
            update = schedule_by_match_id.get(match.match_id)
            if update is None:
                matches.append(match)
                continue
            matches.append(
                match.model_copy(
                    update={
                        "kickoff_time_utc": update.kickoff_time_utc
                        or match.kickoff_time_utc,
                        "status": update.status,
                        "home_score": update.home_score,
                        "away_score": update.away_score,
                        "source": update.provider,
                    }
                )
            )
        return matches

    def list_external_schedule_updates(self) -> list[ExternalScheduleUpdate]:
        return self.external_store.list_schedule_updates()

    def list_external_odds_updates(self, match_id: str | None = None) -> list[ExternalOddsUpdate]:
        return self.external_store.list_odds_updates(match_id)

    async def refresh_external_data(self) -> dict[str, int]:
        if self.external_fetcher is None:
            return {"schedule_updates": 0, "odds_updates": 0}
        schedule_count = await self.external_fetcher.sync_schedule()
        odds_count = await self.external_fetcher.sync_odds()
        return {"schedule_updates": schedule_count, "odds_updates": odds_count}

    def get_lottery_analysis(self, match_id: str) -> LotteryAnalysis | None:
        return self.worldcup.analyze_lottery(match_id, self.store.get_prediction(match_id))

    def get_state(self, match_id: str) -> MatchState | None:
        state = self.store.get_state(match_id)
        if state is not None:
            return state

        match = self.worldcup.get_match(match_id)
        if match is None:
            return None

        state = MatchState(
            match_id=match.match_id,
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            status=match.status,
            match_clock_sec=5400 if match.status == "finished" else 0,
        )
        if match.home_score is not None:
            state.home.score = match.home_score
        if match.away_score is not None:
            state.away.score = match.away_score
        return state

    def get_prediction_evaluation(
        self,
        match_id: str,
        use_settled_fallback: bool = True,
    ) -> PredictionEvaluation | None:
        state = self.get_state(match_id)
        if state is None:
            return None

        prediction = self.store.get_prediction(match_id)
        if prediction is None and use_settled_fallback and state.status == "finished":
            prediction = self.engine.predict(state)

        actual_home = state.home.score if state.status == "finished" else None
        actual_away = state.away.score if state.status == "finished" else None
        actual_total = (
            actual_home + actual_away
            if actual_home is not None and actual_away is not None
            else None
        )

        total_error = None
        brier_score = None
        outcome_hit = None
        actual_over_2_5 = actual_total > 2.5 if actual_total is not None else None
        predicted_over_2_5 = None
        over_2_5_hit = None
        if prediction is not None and actual_home is not None and actual_away is not None:
            actual_outcome = self._outcome_from_score(actual_home, actual_away)
            predicted_outcome = max(
                {
                    "home_win": prediction.home_win,
                    "draw": prediction.draw,
                    "away_win": prediction.away_win,
                },
                key=lambda outcome: {
                    "home_win": prediction.home_win,
                    "draw": prediction.draw,
                    "away_win": prediction.away_win,
                }[outcome],
            )
            total_error = abs(prediction.expected_total_goals - actual_total)
            brier_score = self._brier_score(prediction, actual_outcome)
            outcome_hit = predicted_outcome == actual_outcome
            predicted_over_2_5 = prediction.over_2_5_goals >= prediction.under_2_5_goals
            over_2_5_hit = predicted_over_2_5 == actual_over_2_5

        return PredictionEvaluation(
            match_id=match_id,
            generated_at=datetime.now(UTC),
            source_prediction_version_id=(
                prediction.prediction_version_id if prediction is not None else None
            ),
            status="settled" if actual_total is not None else "pending",
            actual_home_goals=actual_home,
            actual_away_goals=actual_away,
            actual_total_goals=actual_total,
            predicted_home_goals=(
                prediction.expected_home_goals if prediction is not None else None
            ),
            predicted_away_goals=(
                prediction.expected_away_goals if prediction is not None else None
            ),
            predicted_total_goals=(
                prediction.expected_total_goals if prediction is not None else None
            ),
            total_goals_error=round(total_error, 3) if total_error is not None else None,
            actual_over_2_5_goals=actual_over_2_5,
            predicted_over_2_5_goals=predicted_over_2_5,
            over_2_5_hit=over_2_5_hit,
            outcome_brier_score=round(brier_score, 4) if brier_score is not None else None,
            outcome_hit=outcome_hit,
            note=(
                self._evaluation_note(actual_total is not None, prediction is not None)
            ),
        )

    def get_prediction_backtest(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PredictionBacktestReport:
        buckets: dict[date, list[PredictionEvaluation]] = {}
        for match in self.list_worldcup_matches():
            match_date = match.kickoff_time_utc.date()
            if date_from is not None and match_date < date_from:
                continue
            if date_to is not None and match_date > date_to:
                continue
            evaluation = self.get_prediction_evaluation(
                match.match_id,
                use_settled_fallback=False,
            )
            if evaluation is None:
                continue
            buckets.setdefault(match_date, []).append(evaluation)

        bucket_results = [
            self._backtest_bucket(match_date, evaluations)
            for match_date, evaluations in sorted(buckets.items())
        ]
        evaluations = [
            evaluation
            for match_date in sorted(buckets)
            for evaluation in buckets[match_date]
        ]

        return PredictionBacktestReport(
            generated_at=datetime.now(UTC),
            date_from=date_from,
            date_to=date_to,
            match_count=len(evaluations),
            settled_count=sum(1 for item in evaluations if item.status == "settled"),
            pending_count=sum(1 for item in evaluations if item.status == "pending"),
            evaluated_count=sum(1 for item in evaluations if item.outcome_brier_score is not None),
            average_brier_score=self._mean_metric(
                item.outcome_brier_score for item in evaluations
            ),
            total_goals_mae=self._mean_metric(item.total_goals_error for item in evaluations),
            over_2_5_hit_rate=self._hit_rate(item.over_2_5_hit for item in evaluations),
            buckets=bucket_results,
            evaluations=evaluations,
        )

    def _backtest_bucket(
        self,
        match_date: date,
        evaluations: list[PredictionEvaluation],
    ) -> PredictionBacktestBucket:
        return PredictionBacktestBucket(
            date=match_date,
            match_count=len(evaluations),
            settled_count=sum(1 for item in evaluations if item.status == "settled"),
            pending_count=sum(1 for item in evaluations if item.status == "pending"),
            evaluated_count=sum(
                1 for item in evaluations if item.outcome_brier_score is not None
            ),
            average_brier_score=self._mean_metric(
                item.outcome_brier_score for item in evaluations
            ),
            total_goals_mae=self._mean_metric(item.total_goals_error for item in evaluations),
            over_2_5_hit_rate=self._hit_rate(item.over_2_5_hit for item in evaluations),
        )

    def _mean_metric(self, values: Iterable[float | None]) -> float | None:
        numbers = [float(value) for value in values if value is not None]
        if not numbers:
            return None
        return round(sum(numbers) / len(numbers), 4)

    def _hit_rate(self, values: Iterable[bool | None]) -> float | None:
        hits = [bool(value) for value in values if value is not None]
        if not hits:
            return None
        return round(sum(1 for hit in hits if hit) / len(hits), 4)

    def _evaluation_note(self, is_settled: bool, has_prediction: bool) -> str:
        if is_settled and has_prediction:
            return "Finished match evaluated against actual score."
        if is_settled:
            return "Finished match has a final score but no prediction version to score."
        return "Evaluation is pending until the match has a final score."

    def _outcome_from_score(self, home_score: int, away_score: int) -> str:
        if home_score > away_score:
            return "home_win"
        if home_score == away_score:
            return "draw"
        return "away_win"

    def _brier_score(self, prediction: MatchPrediction, actual_outcome: str) -> float:
        probabilities = {
            "home_win": prediction.home_win,
            "draw": prediction.draw,
            "away_win": prediction.away_win,
        }
        return sum(
            (probability - (1.0 if outcome == actual_outcome else 0.0)) ** 2
            for outcome, probability in probabilities.items()
        )

    def _calibrate_goal_projection(
        self,
        event: StandardEvent,
        state: MatchState,
        previous_prediction: MatchPrediction,
    ) -> GoalCalibrationSnapshot | None:
        if event.event_type != "match_finished":
            return None
        if state.status != "finished":
            return None
        actual_total_goals = state.home.score + state.away.score
        return self.engine.calibrate_total_goals(
            match_id=event.match_id,
            predicted_total_goals=previous_prediction.expected_total_goals,
            actual_total_goals=actual_total_goals,
        )

    def list_recent_events(self, limit: int = 20) -> list[EventAuditRecord]:
        return list(reversed(self.event_audit[-limit:]))

    def list_prediction_history(self, match_id: str, limit: int = 20) -> list[MatchPrediction]:
        return self.store.list_prediction_history(match_id, limit)

    def get_latest_simulation(self) -> SimulationResult:
        predictions = self.store.list_predictions()
        return self.simulator.simulate_latest(predictions)

    def get_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            status="ok",
            event_count=self.store.event_count(),
            prediction_count=len(self.store.list_predictions()),
            bus_message_count=self.event_bus.published_count(),
            active_ws_connections=len(self.clients),
        )

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients[websocket] = set()

    def disconnect(self, websocket: WebSocket) -> None:
        self.clients.pop(websocket, None)

    async def handle_subscription(self, websocket: WebSocket, message: dict) -> None:
        if message.get("action") != "subscribe":
            await websocket.send_json({"type": "error", "code": "unsupported_action"})
            return

        match_ids = message.get("match_ids", [])
        if not isinstance(match_ids, list):
            await websocket.send_json({"type": "error", "code": "invalid_match_ids"})
            return

        self.clients[websocket] = {str(match_id) for match_id in match_ids}
        await websocket.send_json(
            {"type": "subscribed", "match_ids": sorted(self.clients[websocket])}
        )

    async def broadcast_prediction(self, prediction: MatchPrediction) -> None:
        stale_clients: list[WebSocket] = []
        for websocket, match_ids in self.clients.items():
            if prediction.match_id not in match_ids:
                continue
            try:
                await websocket.send_json(
                    {
                        "type": "prediction_update",
                        "match_id": prediction.match_id,
                        "prediction_version_id": prediction.prediction_version_id,
                        "generated_at": prediction.generated_at.isoformat(),
                        "home_win": prediction.home_win,
                        "draw": prediction.draw,
                        "away_win": prediction.away_win,
                        "expected_total_goals": prediction.expected_total_goals,
                        "over_2_5_goals": prediction.over_2_5_goals,
                        "under_2_5_goals": prediction.under_2_5_goals,
                        "confidence_level": prediction.confidence_level,
                        "degradation_level": prediction.degradation_level,
                    }
                )
            except RuntimeError:
                stale_clients.append(websocket)

        for websocket in stale_clients:
            self.disconnect(websocket)
