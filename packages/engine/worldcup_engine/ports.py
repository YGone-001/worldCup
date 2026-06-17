from typing import Protocol

from packages.domain.worldcup_domain.schemas import MatchPrediction, MatchState, StandardEvent


class PredictionStore(Protocol):
    def apply_event(self, event: StandardEvent) -> MatchState:
        raise NotImplementedError

    def save_prediction(self, prediction: MatchPrediction) -> None:
        raise NotImplementedError

    def get_prediction(self, match_id: str) -> MatchPrediction | None:
        raise NotImplementedError

    def get_state(self, match_id: str) -> MatchState | None:
        raise NotImplementedError

    def has_event(self, event_id: str) -> bool:
        raise NotImplementedError

    def list_predictions(self) -> list[MatchPrediction]:
        raise NotImplementedError

    def list_prediction_history(self, match_id: str, limit: int = 20) -> list[MatchPrediction]:
        raise NotImplementedError

    def event_count(self) -> int:
        raise NotImplementedError


class EventBus(Protocol):
    def publish_event(self, topic: str, event: StandardEvent) -> None:
        raise NotImplementedError

    def publish_prediction(self, topic: str, prediction: MatchPrediction) -> None:
        raise NotImplementedError

    def published_count(self, topic: str | None = None) -> int:
        raise NotImplementedError
