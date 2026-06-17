from packages.domain.worldcup_domain.schemas import MatchPrediction, MatchState, StandardEvent


class InMemoryPredictionStore:
    def __init__(self) -> None:
        self.states: dict[str, MatchState] = {}
        self.predictions: dict[str, MatchPrediction] = {}
        self.prediction_history: dict[str, list[MatchPrediction]] = {}
        self.seen_events: set[str] = set()

    def apply_event(self, event: StandardEvent) -> MatchState:
        if event.event_id in self.seen_events and not event.correction_flag:
            return self.states.get(event.match_id, MatchState(match_id=event.match_id))

        self.seen_events.add(event.event_id)
        state = self.states.get(event.match_id)
        if state is None:
            state = MatchState(match_id=event.match_id)

        state.status = self._next_status(state.status, event.event_type)
        state.period = max(state.period, event.period)
        state.match_clock_sec = max(state.match_clock_sec, event.match_clock_sec)
        state.last_event_id = event.event_id
        state.last_event_time = event.event_time

        side = self._resolve_side(event, state)
        team_state = state.home if side == "home" else state.away

        if event.event_type == "goal":
            team_state.score += 1
        elif event.event_type == "shot":
            team_state.shots += 1
            team_state.xg += float(event.payload.get("xg", 0.08))
        elif event.event_type == "xg_update":
            team_state.xg = float(event.payload.get("xg", team_state.xg))
        elif event.event_type == "red_card":
            team_state.red_cards += 1
        elif event.event_type == "yellow_card":
            team_state.yellow_cards += 1

        self.states[event.match_id] = state
        return state

    def save_prediction(self, prediction: MatchPrediction) -> None:
        self.predictions[prediction.match_id] = prediction
        self.prediction_history.setdefault(prediction.match_id, []).append(prediction)

    def get_prediction(self, match_id: str) -> MatchPrediction | None:
        return self.predictions.get(match_id)

    def get_state(self, match_id: str) -> MatchState | None:
        return self.states.get(match_id)

    def has_event(self, event_id: str) -> bool:
        return event_id in self.seen_events

    def list_predictions(self) -> list[MatchPrediction]:
        return list(self.predictions.values())

    def list_prediction_history(self, match_id: str, limit: int = 20) -> list[MatchPrediction]:
        history = self.prediction_history.get(match_id, [])
        return list(reversed(history[-limit:]))

    def event_count(self) -> int:
        return len(self.seen_events)

    def _resolve_side(self, event: StandardEvent, state: MatchState) -> str:
        if event.team_id == state.away_team_id or event.payload.get("side") == "away":
            return "away"
        return "home"

    def _next_status(self, current: str, event_type: str) -> str:
        if event_type == "match_started":
            return "live"
        if event_type == "match_finished":
            return "finished"
        if current == "scheduled":
            return "live"
        return current
