from __future__ import annotations

from typing import Any
import json

from packages.domain.worldcup_domain.schemas import StandardEvent


RAW_EVENTS_TOPIC = "worldcup.events.raw"
PREDICTIONS_UPDATED_TOPIC = "worldcup.predictions.updated"


class KafkaEventBus:
    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str = "worldcup-prediction-engine",
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._producer: Any | None = None
        self._published_count = 0

    async def connect(self) -> None:
        if self._producer is not None:
            return

        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            client_id=self.client_id,
            acks="all",
        )
        await self._producer.start()

    async def disconnect(self) -> None:
        if self._producer is None:
            return

        await self._producer.stop()
        self._producer = None

    async def publish_event(self, topic: str, event: StandardEvent) -> None:
        payload = event.model_dump(mode="json")
        partition_key = str(payload["match_id"])
        await self.publish_json(topic, payload, partition_key=partition_key)

    async def publish_json(
        self,
        topic: str,
        payload: dict[str, Any],
        partition_key: str,
    ) -> None:
        if self._producer is None:
            raise RuntimeError("kafka_producer_not_connected")

        value = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        key = partition_key.encode("utf-8")
        await self._producer.send_and_wait(topic, value=value, key=key)
        self._published_count += 1

    def published_count(self, topic: str | None = None) -> int:
        return self._published_count

