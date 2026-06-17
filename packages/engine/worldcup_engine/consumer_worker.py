from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
import asyncio
import contextlib
import json

from packages.domain.worldcup_domain.schemas import (
    EventAuditRecord,
    MatchPrediction,
    StandardEvent,
)
from packages.engine.worldcup_engine.event_bus_kafka import (
    KafkaEventBus,
    PREDICTIONS_UPDATED_TOPIC,
    RAW_EVENTS_TOPIC,
)


PredictionCallback = Callable[[MatchPrediction], Awaitable[None]]


class KafkaPredictionConsumerWorker:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        store: Any,
        quality: Any,
        engine: Any,
        worldcup: Any,
        prediction_bus: KafkaEventBus,
        event_audit: list[EventAuditRecord],
        raw_topic: str = RAW_EVENTS_TOPIC,
        prediction_topic: str = PREDICTIONS_UPDATED_TOPIC,
        on_prediction: PredictionCallback | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.raw_topic = raw_topic
        self.prediction_topic = prediction_topic
        self.store = store
        self.quality = quality
        self.engine = engine
        self.worldcup = worldcup
        self.prediction_bus = prediction_bus
        self.event_audit = event_audit
        self.on_prediction = on_prediction
        self._consumer: Any | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return

        from aiokafka import AIOKafkaConsumer

        self._consumer = AIOKafkaConsumer(
            self.raw_topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )
        await self._consumer.start()
        self._task = asyncio.create_task(self._run(), name="worldcup-kafka-consumer")

    async def stop(self) -> None:
        self._stopping.set()

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def _run(self) -> None:
        if self._consumer is None:
            return

        while not self._stopping.is_set():
            try:
                message = await self._consumer.getone()
                await self.process_message(message.value)
                await self._consumer.commit()
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.5)

    async def process_message(self, value: bytes | str | dict[str, Any]) -> MatchPrediction | None:
        payload = self._decode_payload(value)
        event = StandardEvent.model_validate(payload)

        if self.store.has_event(event.event_id):
            self.event_audit.append(
                EventAuditRecord(
                    event_id=event.event_id,
                    match_id=event.match_id,
                    event_type=event.event_type,
                    event_time=event.event_time,
                    received_at=datetime.now(UTC),
                    source=event.source,
                    accepted=False,
                    score=0.0,
                    warnings=["duplicate_event"],
                )
            )
            return None

        quality = self.quality.inspect(event, duplicate=False)
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

        if not quality.accepted:
            return None

        previous_prediction = self.store.get_prediction(event.match_id)
        match_state = self.store.apply_event(event)
        if event.event_type == "match_finished" and previous_prediction is not None:
            self.engine.calibrate_total_goals(
                match_id=event.match_id,
                predicted_total_goals=previous_prediction.expected_total_goals,
                actual_total_goals=match_state.home.score + match_state.away.score,
            )
        prediction = self.engine.predict(match_state)
        self.store.save_prediction(prediction)

        payload_to_publish = self._prediction_update_payload(event, prediction)
        await self.prediction_bus.publish_json(
            self.prediction_topic,
            payload_to_publish,
            partition_key=event.match_id,
        )

        if self.on_prediction is not None:
            await self.on_prediction(prediction)

        return prediction

    def _prediction_update_payload(
        self,
        event: StandardEvent,
        prediction: MatchPrediction,
    ) -> dict[str, Any]:
        analysis = self.worldcup.analyze_lottery(event.match_id, prediction)
        if analysis is not None:
            return analysis.model_dump(mode="json")

        return {
            "match_id": event.match_id,
            "generated_at": prediction.generated_at.isoformat(),
            "source_prediction_version_id": prediction.prediction_version_id,
            "outcomes": [
                self._outcome("home_win", prediction.home_win),
                self._outcome("draw", prediction.draw),
                self._outcome("away_win", prediction.away_win),
            ],
            "expected_total_goals": prediction.expected_total_goals,
            "over_2_5_goals": prediction.over_2_5_goals,
            "under_2_5_goals": prediction.under_2_5_goals,
            "confidence_level": prediction.confidence_level,
            "settlement_status": "open",
        }

    def _outcome(self, code: str, probability: float) -> dict[str, Any]:
        safe_probability = max(0.001, min(0.999, probability))
        return {
            "code": code,
            "probability": round(safe_probability, 4),
            "fair_decimal_odds": round(1.0 / safe_probability, 3),
        }

    def _decode_payload(self, value: bytes | str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, bytes):
            return json.loads(value.decode("utf-8"))
        return json.loads(value)
