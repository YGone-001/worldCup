from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
import logging
import os

from packages.engine.worldcup_engine.adapters.id_mapping import StaticExternalMatchIdMapper
from packages.engine.worldcup_engine.adapters.schemas import (
    ExternalOddsUpdate,
    ExternalScheduleUpdate,
)
from packages.engine.worldcup_engine.adapters.store import ExternalDataStore
from packages.engine.worldcup_engine.adapters.transformers import ExternalDataTransformer


EXTERNAL_SCHEDULE_TOPIC = "worldcup.schedule.external"
EXTERNAL_ODDS_TOPIC = "worldcup.odds.external"
DEFAULT_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/"
    "scoreboard?dates=20260611-20260719"
)
DEFAULT_ODDS_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchListV1.qry?clientCode=3001"
)


class JsonPublisher(Protocol):
    async def publish_json(
        self,
        topic: str,
        payload: dict[str, Any],
        partition_key: str,
    ) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class ExternalFetcherConfig:
    provider: str
    schedule_provider: str | None = None
    odds_provider: str | None = None
    schedule_url: str | None = None
    odds_url: str | None = None
    schedule_topic: str = EXTERNAL_SCHEDULE_TOPIC
    odds_topic: str = EXTERNAL_ODDS_TOPIC
    schedule_interval_seconds: int = 60
    odds_interval_seconds: int = 10
    request_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> ExternalFetcherConfig:
        return cls(
            provider=os.getenv("WORLDCUP_EXTERNAL_PROVIDER", "external"),
            schedule_provider=os.getenv("WORLDCUP_SCHEDULE_PROVIDER", "espn"),
            odds_provider=os.getenv("WORLDCUP_ODDS_PROVIDER", "sporttery"),
            schedule_url=os.getenv("WORLDCUP_SCHEDULE_API_URL", DEFAULT_SCHEDULE_URL) or None,
            odds_url=os.getenv("WORLDCUP_ODDS_API_URL", DEFAULT_ODDS_URL) or None,
            schedule_topic=os.getenv(
                "WORLDCUP_KAFKA_EXTERNAL_SCHEDULE_TOPIC",
                EXTERNAL_SCHEDULE_TOPIC,
            ),
            odds_topic=os.getenv("WORLDCUP_KAFKA_EXTERNAL_ODDS_TOPIC", EXTERNAL_ODDS_TOPIC),
            schedule_interval_seconds=int(os.getenv("WORLDCUP_SCHEDULE_SYNC_INTERVAL", "60")),
            odds_interval_seconds=int(os.getenv("WORLDCUP_ODDS_SYNC_INTERVAL", "10")),
            request_timeout_seconds=float(os.getenv("WORLDCUP_EXTERNAL_HTTP_TIMEOUT", "5.0")),
        )


class ExternalFetcherService:
    def __init__(
        self,
        config: ExternalFetcherConfig,
        publisher: JsonPublisher,
        transformer: ExternalDataTransformer | None = None,
        store: ExternalDataStore | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.publisher = publisher
        self.transformer = transformer or ExternalDataTransformer(
            StaticExternalMatchIdMapper.from_env()
        )
        self.store = store
        self.logger = logger or logging.getLogger(__name__)
        self._client: Any | None = None
        self._scheduler: Any | None = None

    async def start(self) -> None:
        if self._scheduler is not None:
            return

        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        import httpx

        self._client = httpx.AsyncClient(timeout=self.config.request_timeout_seconds)
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        if self.config.schedule_url is not None:
            self._scheduler.add_job(
                self.sync_schedule,
                "interval",
                seconds=self.config.schedule_interval_seconds,
                id="worldcup-external-schedule-sync",
                max_instances=1,
                coalesce=True,
            )
        if self.config.odds_url is not None:
            self._scheduler.add_job(
                self.sync_odds,
                "interval",
                seconds=self.config.odds_interval_seconds,
                id="worldcup-external-odds-sync",
                max_instances=1,
                coalesce=True,
            )
        self._scheduler.start()

    async def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def sync_schedule(self) -> int:
        if self.config.schedule_url is None:
            return 0
        payload = await self._fetch_json(self.config.schedule_url, "schedule")
        if payload is None:
            return 0
        updates = self.transformer.transform_schedule_payload(self.schedule_provider, payload)
        for update in updates:
            await self._publish_schedule(update)
            if self.store is not None:
                self.store.upsert_schedule(update)
        return len(updates)

    async def sync_odds(self) -> int:
        if self.config.odds_url is None:
            return 0
        payload = await self._fetch_json(self.config.odds_url, "odds")
        if payload is None:
            return 0
        updates = self.transformer.transform_odds_payload(self.odds_provider, payload)
        for update in updates:
            await self._publish_odds(update)
            if self.store is not None:
                self.store.upsert_odds(update)
        return len(updates)

    async def _fetch_json(self, url: str, label: str) -> Any | None:
        try:
            client = self._require_client()
            response = await client.get(url, headers=self._headers_for_url(url))
            response.raise_for_status()
            return response.json()
        except self._httpx_errors() as exc:
            self.logger.warning("external_%s_http_error url=%s error=%s", label, url, exc)
            return None
        except ValueError as exc:
            self.logger.warning("external_%s_json_decode_error url=%s error=%s", label, url, exc)
            return None

    async def _publish_schedule(self, update: ExternalScheduleUpdate) -> None:
        await self.publisher.publish_json(
            self.config.schedule_topic,
            update.model_dump(mode="json"),
            partition_key=update.match_id,
        )

    async def _publish_odds(self, update: ExternalOddsUpdate) -> None:
        await self.publisher.publish_json(
            self.config.odds_topic,
            update.model_dump(mode="json"),
            partition_key=update.match_id,
        )

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("external_fetcher_not_started")
        return self._client

    @property
    def schedule_provider(self) -> str:
        return self.config.schedule_provider or self.config.provider

    @property
    def odds_provider(self) -> str:
        return self.config.odds_provider or self.config.provider

    def _headers_for_url(self, url: str) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        if "sporttery.cn" in url:
            headers.update(
                {
                    "Referer": "https://www.sporttery.cn/jc/jsq/zqspf/",
                    "Origin": "https://www.sporttery.cn",
                    "Sec-Fetch-Site": "same-site",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                }
            )
        return headers

    def _httpx_errors(self) -> type[Exception]:
        import httpx

        return httpx.HTTPError
