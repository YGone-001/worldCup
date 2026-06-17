from datetime import UTC, datetime
import asyncio
import json
import unittest

from packages.domain.worldcup_domain.schemas import EventAuditRecord, StandardEvent
from packages.engine.worldcup_engine.aggregator import PredictionAggregator
from packages.engine.worldcup_engine.consumer_worker import KafkaPredictionConsumerWorker
from packages.engine.worldcup_engine.event_bus_kafka import KafkaEventBus
from packages.engine.worldcup_engine.predictor import BaselinePredictionEngine
from packages.engine.worldcup_engine.quality import DataQualityService
from packages.engine.worldcup_engine.storage import InMemoryPredictionStore
from packages.engine.worldcup_engine.worldcup_progress import WorldCupProgressProvider


class FakeProducer:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_and_wait(self, topic: str, value: bytes, key: bytes) -> None:
        self.sent.append({"topic": topic, "value": value, "key": key})


class FakePredictionBus:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def publish_json(self, topic: str, payload: dict, partition_key: str) -> None:
        self.messages.append(
            {
                "topic": topic,
                "payload": payload,
                "partition_key": partition_key,
            }
        )


class KafkaEventBusTest(unittest.TestCase):
    def test_publish_event_uses_match_id_as_partition_key(self) -> None:
        producer = FakeProducer()
        bus = KafkaEventBus("localhost:19092")
        bus._producer = producer
        event = StandardEvent(
            event_id="evt_kafka_key_1",
            match_id="match_partition_1",
            event_type="goal",
            event_time=datetime.now(UTC),
            team_id="home",
            payload={"side": "home"},
        )

        asyncio.run(bus.publish_event("worldcup.events.raw", event))

        self.assertEqual(producer.sent[0]["key"], b"match_partition_1")
        self.assertEqual(producer.sent[0]["topic"], "worldcup.events.raw")


class KafkaConsumerWorkerTest(unittest.TestCase):
    def test_consumer_worker_blocks_duplicate_event_id(self) -> None:
        store = InMemoryPredictionStore()
        quality = DataQualityService()
        engine = BaselinePredictionEngine(PredictionAggregator())
        worldcup = WorldCupProgressProvider()
        prediction_bus = FakePredictionBus()
        event_audit: list[EventAuditRecord] = []
        worker = KafkaPredictionConsumerWorker(
            bootstrap_servers="localhost:19092",
            group_id="test-group",
            store=store,
            quality=quality,
            engine=engine,
            worldcup=worldcup,
            prediction_bus=prediction_bus,
            event_audit=event_audit,
        )
        event = StandardEvent(
            event_id="evt_duplicate_kafka_1",
            match_id="wc2026_can_bih",
            event_type="shot",
            event_time=datetime.now(UTC),
            team_id="home",
            match_clock_sec=120,
            payload={"xg": 0.12, "side": "home"},
        )
        message = json.dumps(event.model_dump(mode="json")).encode("utf-8")

        first_prediction = asyncio.run(worker.process_message(message))
        second_prediction = asyncio.run(worker.process_message(message))

        self.assertIsNotNone(first_prediction)
        self.assertIsNone(second_prediction)
        self.assertEqual(store.event_count(), 1)
        self.assertEqual(len(prediction_bus.messages), 1)
        self.assertEqual(prediction_bus.messages[0]["partition_key"], "wc2026_can_bih")
        self.assertIn("outcomes", prediction_bus.messages[0]["payload"])
        self.assertIn("fair_decimal_odds", prediction_bus.messages[0]["payload"]["outcomes"][0])
        self.assertEqual(len(event_audit), 2)
        self.assertFalse(event_audit[1].accepted)
        self.assertIn("duplicate_event", event_audit[1].warnings)


if __name__ == "__main__":
    unittest.main()
