from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from packages.engine.worldcup_engine.adapters.id_mapping import ExternalMatchIdMapper
from packages.engine.worldcup_engine.adapters.schemas import (
    ExternalOddsUpdate,
    ExternalScheduleUpdate,
    OddsSelection,
)


class TransformError(Exception):
    def __init__(
        self,
        code: str,
        provider: str,
        external_match_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.provider = provider
        self.external_match_id = external_match_id
        self.detail = detail


class ExternalDataTransformer:
    def __init__(self, mapper: ExternalMatchIdMapper) -> None:
        self.mapper = mapper

    def transform_schedule_payload(
        self,
        provider: str,
        payload: Any,
    ) -> list[ExternalScheduleUpdate]:
        updates: list[ExternalScheduleUpdate] = []
        for record in self._records(payload, "matches"):
            try:
                updates.append(self.transform_schedule_record(provider, record))
            except TransformError:
                continue
        return updates

    def transform_odds_payload(
        self,
        provider: str,
        payload: Any,
    ) -> list[ExternalOddsUpdate]:
        updates: list[ExternalOddsUpdate] = []
        for record in self._records(payload, "odds"):
            try:
                updates.extend(self._transform_odds_record_list(provider, record))
            except TransformError:
                continue
        return updates

    def _transform_odds_record_list(
        self,
        provider: str,
        record: MappingLike,
    ) -> list[ExternalOddsUpdate]:
        data = self._expect_dict(provider, record)
        if "oddsList" in data or "had" in data or "hhad" in data:
            return self._transform_sporttery_odds_record(provider, data)
        return [self.transform_odds_record(provider, data)]

    def transform_schedule_record(
        self,
        provider: str,
        record: MappingLike,
    ) -> ExternalScheduleUpdate:
        try:
            data = self._expect_dict(provider, record)
            external_match_id = self._string_value(
                data,
                "external_match_id",
                "matchId",
                "match_id",
                "id",
            )
            match_id = self._resolve(provider, external_match_id)
            status = self._normalize_status(
                self._optional_scalar_string(
                    self._first_present(data, "status", "match_status", "matchStatus", "state")
                )
                or self._espn_status(data)
                or "scheduled",
            )
            home_score = self._optional_int(
                self._first_not_none(
                    self._first_present(data, "home_score", "homeScore"),
                    self._espn_score(data, "home"),
                )
            )
            away_score = self._optional_int(
                self._first_not_none(
                    self._first_present(data, "away_score", "awayScore"),
                    self._espn_score(data, "away"),
                )
            )
            if status == "scheduled":
                home_score = None
                away_score = None
            return ExternalScheduleUpdate(
                event_id=self._event_id(provider, external_match_id, "schedule", data),
                provider=provider,
                external_match_id=external_match_id,
                match_id=match_id,
                status=status,
                kickoff_time_utc=self._optional_datetime(
                    self._first_present(
                        data,
                        "kickoff_time_utc",
                        "kickoffTimeUtc",
                        "kickoff_time",
                        "startTime",
                    )
                    or self._sporttery_kickoff(data)
                    or data.get("date")
                ),
                home_score=home_score,
                away_score=away_score,
                observed_at=self._optional_datetime(
                    self._first_present(data, "observed_at", "updatedAt", "timestamp")
                )
                or datetime.now(UTC),
                source_payload=self._compact_source_payload(data),
            )
        except TransformError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise TransformError(
                "invalid_schedule_record",
                provider,
                self._best_effort_external_match_id(record),
                str(exc),
            ) from exc

    def transform_odds_record(
        self,
        provider: str,
        record: MappingLike,
    ) -> ExternalOddsUpdate:
        try:
            data = self._expect_dict(provider, record)
            external_match_id = self._string_value(
                data,
                "external_match_id",
                "matchId",
                "match_id",
                "id",
            )
            match_id = self._resolve(provider, external_match_id)
            market = self._normalize_market(
                self._string_value(data, "market", "market_code", "gameType")
            )
            selections = self._extract_selections(provider, external_match_id, data)
            return ExternalOddsUpdate(
                event_id=self._event_id(provider, external_match_id, market, data),
                provider=provider,
                external_match_id=external_match_id,
                match_id=match_id,
                lottery_match_no=self._optional_string(
                    data.get("lottery_match_no") or data.get("lotteryMatchNo")
                ),
                market=market,
                handicap=self._optional_float(self._first_present(data, "handicap", "rq")),
                selections=selections,
                observed_at=self._optional_datetime(
                    self._first_present(data, "observed_at", "updatedAt", "timestamp")
                )
                or datetime.now(UTC),
                version=self._optional_string(self._first_present(data, "version", "oddsVersion")),
                source_payload=self._compact_source_payload(data),
            )
        except TransformError:
            raise
        except (TypeError, ValueError, ValidationError) as exc:
            raise TransformError(
                "invalid_odds_record",
                provider,
                self._best_effort_external_match_id(record),
                str(exc),
            ) from exc

    def _extract_selections(
        self,
        provider: str,
        external_match_id: str,
        data: dict[str, Any],
    ) -> list[OddsSelection]:
        if isinstance(data.get("selections"), list):
            return [
                OddsSelection(
                    outcome=self._normalize_outcome(
                        self._string_value(selection, "outcome", "code", "name")
                    ),
                    decimal_odds=self._float_value(selection, "decimal_odds", "odds", "value"),
                    water_level=self._optional_float(
                        self._first_present(selection, "water_level", "water")
                    ),
                )
                for selection in data["selections"]
                if isinstance(selection, dict)
            ]

        try:
            return [
                OddsSelection(
                    outcome="home_win",
                    decimal_odds=self._float_value(data, "home_win", "homeWin", "win"),
                    water_level=self._optional_float(
                        self._first_present(data, "home_water", "winWater")
                    ),
                ),
                OddsSelection(
                    outcome="draw",
                    decimal_odds=self._float_value(data, "draw", "draw_odds", "drawOdds"),
                    water_level=self._optional_float(
                        self._first_present(data, "draw_water", "drawWater")
                    ),
                ),
                OddsSelection(
                    outcome="away_win",
                    decimal_odds=self._float_value(data, "away_win", "awayWin", "lose"),
                    water_level=self._optional_float(
                        self._first_present(data, "away_water", "loseWater")
                    ),
                ),
            ]
        except (TypeError, ValueError, ValidationError) as exc:
            raise TransformError(
                "invalid_odds_selection",
                provider,
                external_match_id,
                str(exc),
            ) from exc

    def _transform_sporttery_odds_record(
        self,
        provider: str,
        data: dict[str, Any],
    ) -> list[ExternalOddsUpdate]:
        external_match_id = self._string_value(data, "matchId", "external_match_id", "id")
        match_id = self._resolve(provider, external_match_id)
        updates: list[ExternalOddsUpdate] = []
        pool_records = self._sporttery_pool_records(data)

        for pool_code, pool_data in pool_records:
            market = self._normalize_market(pool_code)
            try:
                updates.append(
                    ExternalOddsUpdate(
                        event_id=self._event_id(provider, external_match_id, market, pool_data),
                        provider=provider,
                        external_match_id=external_match_id,
                        match_id=match_id,
                        lottery_match_no=self._optional_string(
                            self._first_present(data, "matchNumStr", "matchNum")
                        ),
                        market=market,
                        handicap=self._optional_float(pool_data.get("goalLine")),
                        selections=[
                            OddsSelection(
                                outcome="home_win",
                                decimal_odds=self._float_value(pool_data, "h"),
                            ),
                            OddsSelection(
                                outcome="draw",
                                decimal_odds=self._float_value(pool_data, "d"),
                            ),
                            OddsSelection(
                                outcome="away_win",
                                decimal_odds=self._float_value(pool_data, "a"),
                            ),
                        ],
                        observed_at=self._sporttery_observed_at(pool_data),
                        version=self._optional_string(
                            self._first_present(pool_data, "oddsVersion", "updateTime")
                        ),
                        source_payload=self._compact_source_payload(data),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise TransformError(
                    "invalid_sporttery_odds_record",
                    provider,
                    external_match_id,
                    str(exc),
                ) from exc
        return updates

    def _sporttery_pool_records(self, data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        records: list[tuple[str, dict[str, Any]]] = []
        odds_list = data.get("oddsList")
        if isinstance(odds_list, list):
            for item in odds_list:
                if not isinstance(item, dict):
                    continue
                pool_code = self._optional_string(item.get("poolCode"))
                if pool_code in {"HAD", "HHAD", "had", "hhad"}:
                    records.append((pool_code, item))
        for key, pool_code in (("had", "HAD"), ("hhad", "HHAD")):
            value = data.get(key)
            if isinstance(value, dict) and value:
                records.append((pool_code, value))
        return records

    def _resolve(self, provider: str, external_match_id: str) -> str:
        match_id = self.mapper.resolve_match_id(provider, external_match_id)
        if match_id is None:
            raise TransformError("match_id_mapping_not_found", provider, external_match_id)
        return match_id

    def _records(self, payload: Any, key: str) -> Iterable[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            events = payload.get("events")
            if isinstance(events, list):
                return events
            nested = self._sporttery_records(payload)
            if nested:
                return nested
            value = payload.get(key) or payload.get("data") or payload.get("items")
            if isinstance(value, list):
                return value
            return [payload]
        return []

    def _sporttery_records(self, payload: dict[str, Any]) -> list[Any]:
        value = payload.get("value")
        if not isinstance(value, dict):
            return []
        match_info_list = value.get("matchInfoList")
        if not isinstance(match_info_list, list):
            return []
        records: list[Any] = []
        for group in match_info_list:
            if not isinstance(group, dict):
                continue
            sub_match_list = group.get("subMatchList")
            if isinstance(sub_match_list, list):
                records.extend(sub_match_list)
        return records

    def _expect_dict(self, provider: str, record: MappingLike) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise TransformError("record_is_not_object", provider)
        return record

    def _string_value(self, data: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise ValueError(f"missing_string:{keys[0]}")

    def _float_value(self, data: dict[str, Any], *keys: str) -> float:
        for key in keys:
            value = data.get(key)
            if value is not None:
                return float(value)
        raise ValueError(f"missing_float:{keys[0]}")

    def _first_present(self, data: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in data:
                return data[key]
        return None

    def _first_not_none(self, *values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _optional_scalar_string(self, value: Any) -> str | None:
        if isinstance(value, (dict, list, tuple, set)):
            return None
        return self._optional_string(value)

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    def _optional_float(self, value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    def _optional_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(float(value), UTC)
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _normalize_status(self, status: str) -> str:
        normalized = status.strip().lower()
        mapping = {
            "not_started": "scheduled",
            "pre": "scheduled",
            "fixture": "scheduled",
            "status_scheduled": "scheduled",
            "selling": "scheduled",
            "stop": "scheduled",
            "in_progress": "live",
            "running": "live",
            "status_in_progress": "live",
            "ft": "finished",
            "ended": "finished",
            "complete": "finished",
            "status_full_time": "finished",
        }
        return mapping.get(normalized, normalized)

    def _normalize_market(self, market: str) -> str:
        normalized = market.strip().lower()
        mapping = {
            "spf": "win_draw_win",
            "had": "win_draw_win",
            "HAD": "win_draw_win",
            "1x2": "win_draw_win",
            "rqspf": "handicap_win_draw_win",
            "hhad": "handicap_win_draw_win",
            "HHAD": "handicap_win_draw_win",
            "handicap": "handicap_win_draw_win",
        }
        return mapping.get(normalized, normalized)

    def _normalize_outcome(self, outcome: str) -> str:
        normalized = outcome.strip().lower()
        mapping = {
            "h": "home_win",
            "home": "home_win",
            "win": "home_win",
            "3": "home_win",
            "d": "draw",
            "x": "draw",
            "1": "draw",
            "a": "away_win",
            "away": "away_win",
            "lose": "away_win",
            "0": "away_win",
        }
        return mapping.get(normalized, normalized)

    def _event_id(
        self,
        provider: str,
        external_match_id: str,
        kind: str,
        data: dict[str, Any],
    ) -> str:
        source = "|".join(
            [
                provider,
                external_match_id,
                kind,
                str(data.get("updatedAt") or data.get("timestamp") or data.get("version") or data),
            ]
        )
        digest = sha256(source.encode("utf-8")).hexdigest()[:24]
        return f"ext_{digest}"

    def _best_effort_external_match_id(self, record: Any) -> str | None:
        if not isinstance(record, dict):
            return None
        for key in ("external_match_id", "matchId", "match_id", "id"):
            value = record.get(key)
            if value is not None:
                return str(value)
        return None

    def _sporttery_kickoff(self, data: dict[str, Any]) -> datetime | None:
        match_date = self._optional_string(data.get("matchDate"))
        match_time = self._optional_string(data.get("matchTime"))
        if match_date is None or match_time is None:
            return None
        local_value = datetime.fromisoformat(f"{match_date}T{match_time}:00")
        return local_value.replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(UTC)

    def _sporttery_observed_at(self, data: dict[str, Any]) -> datetime:
        update_date = self._optional_string(data.get("updateDate"))
        update_time = self._optional_string(data.get("updateTime"))
        if update_date is not None and update_time is not None:
            local_value = datetime.fromisoformat(f"{update_date}T{update_time}")
            return local_value.replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(UTC)
        return datetime.now(UTC)

    def _compact_source_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "id",
            "matchId",
            "matchNum",
            "matchNumStr",
            "matchStatus",
            "matchDate",
            "matchTime",
            "date",
            "name",
            "shortName",
            "poolCode",
            "goalLine",
            "h",
            "d",
            "a",
            "updateDate",
            "updateTime",
        )
        return {key: data[key] for key in keys if key in data}

    def _espn_status(self, data: dict[str, Any]) -> str | None:
        competitions = data.get("competitions")
        if not isinstance(competitions, list) or not competitions:
            return None
        status = competitions[0].get("status")
        if not isinstance(status, dict):
            return None
        status_type = status.get("type")
        if not isinstance(status_type, dict):
            return None
        return self._optional_string(status_type.get("name") or status_type.get("state"))

    def _espn_score(self, data: dict[str, Any], side: str) -> int | None:
        competitions = data.get("competitions")
        if not isinstance(competitions, list) or not competitions:
            return None
        competitors = competitions[0].get("competitors")
        if not isinstance(competitors, list):
            return None
        for competitor in competitors:
            if not isinstance(competitor, dict):
                continue
            if competitor.get("homeAway") != side:
                continue
            score = competitor.get("score")
            if score is None:
                return None
            return int(score)
        return None


MappingLike = dict[str, Any]
