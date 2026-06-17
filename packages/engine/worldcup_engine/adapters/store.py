from __future__ import annotations

from packages.engine.worldcup_engine.adapters.schemas import (
    ExternalOddsUpdate,
    ExternalScheduleUpdate,
)


class ExternalDataStore:
    def __init__(self) -> None:
        self.schedule_updates: dict[str, ExternalScheduleUpdate] = {}
        self.odds_updates: dict[str, dict[str, ExternalOddsUpdate]] = {}

    def upsert_schedule(self, update: ExternalScheduleUpdate) -> None:
        current = self.schedule_updates.get(update.match_id)
        if current is None or update.observed_at >= current.observed_at:
            self.schedule_updates[update.match_id] = update

    def upsert_odds(self, update: ExternalOddsUpdate) -> None:
        by_market = self.odds_updates.setdefault(update.match_id, {})
        current = by_market.get(update.market)
        if current is None or update.observed_at >= current.observed_at:
            by_market[update.market] = update

    def list_schedule_updates(self) -> list[ExternalScheduleUpdate]:
        return sorted(
            self.schedule_updates.values(),
            key=lambda update: (update.kickoff_time_utc is None, update.kickoff_time_utc),
        )

    def list_odds_updates(self, match_id: str | None = None) -> list[ExternalOddsUpdate]:
        if match_id is not None:
            return sorted(
                self.odds_updates.get(match_id, {}).values(),
                key=lambda update: update.market,
            )
        updates: list[ExternalOddsUpdate] = []
        for by_market in self.odds_updates.values():
            updates.extend(by_market.values())
        return sorted(updates, key=lambda update: (update.match_id, update.market))
