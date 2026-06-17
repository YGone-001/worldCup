from datetime import UTC, datetime
from pathlib import Path
import json

from packages.domain.worldcup_domain.schemas import MatchPrediction, StandardEvent


NORMALIZED_MATCH_EVENTS_TOPIC = "normalized.match.events"
PREDICTIONS_LIVE_TOPIC = "predictions.live"


class InMemoryEventBus:
    def __init__(self) -> None:
        self.messages: dict[str, list[dict]] = {}

    def publish_event(self, topic: str, event: StandardEvent) -> None:
        self._append(topic, event.model_dump(mode="json"))

    def publish_prediction(self, topic: str, prediction: MatchPrediction) -> None:
        self._append(topic, prediction.model_dump(mode="json"))

    async def publish_json(self, topic: str, payload: dict, partition_key: str) -> None:
        self._append(topic, payload)

    def published_count(self, topic: str | None = None) -> int:
        if topic is not None:
            return len(self.messages.get(topic, []))
        return sum(len(messages) for messages in self.messages.values())

    def _append(self, topic: str, payload: dict) -> None:
        self.messages.setdefault(topic, []).append(
            {
                "topic": topic,
                "published_at": datetime.now(UTC).isoformat(),
                "payload": payload,
            }
        )


class JsonlEventBus(InMemoryEventBus):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _append(self, topic: str, payload: dict) -> None:
        super()._append(topic, payload)
        record = {
            "topic": topic,
            "published_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        file_path = self.root / f"{topic}.jsonl"
        with file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")))
            file.write("\n")
