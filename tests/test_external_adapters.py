from datetime import UTC, datetime
import asyncio
import unittest

from packages.engine.worldcup_engine.adapters.external_fetcher import (
    EXTERNAL_ODDS_TOPIC,
    EXTERNAL_SCHEDULE_TOPIC,
    ExternalFetcherConfig,
    ExternalFetcherService,
)
from packages.engine.worldcup_engine.adapters.id_mapping import (
    DEFAULT_EXTERNAL_MATCH_ID_MAP,
    StaticExternalMatchIdMapper,
)
from packages.engine.worldcup_engine.adapters.transformers import (
    ExternalDataTransformer,
    TransformError,
)


class FakePublisher:
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


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def get(self, url: str, headers: dict | None = None) -> FakeResponse:
        return FakeResponse(self.payload)


class ExternalAdapterTest(unittest.TestCase):
    def _transformer(self) -> ExternalDataTransformer:
        mapper = StaticExternalMatchIdMapper()
        mapper.add("provider-a", "ext-1", "wc2026_can_bih")
        return ExternalDataTransformer(mapper)

    def test_schedule_transformer_resolves_external_match_id(self) -> None:
        update = self._transformer().transform_schedule_record(
            "provider-a",
            {
                "matchId": "ext-1",
                "status": "ft",
                "kickoffTimeUtc": "2026-06-12T19:00:00Z",
                "homeScore": 0,
                "awayScore": 0,
            },
        )

        self.assertEqual(update.match_id, "wc2026_can_bih")
        self.assertEqual(update.status, "finished")
        self.assertEqual(update.home_score, 0)
        self.assertEqual(update.away_score, 0)

    def test_odds_transformer_normalizes_handicap_market(self) -> None:
        update = self._transformer().transform_odds_record(
            "provider-a",
            {
                "matchId": "ext-1",
                "market": "rqspf",
                "rq": 0,
                "win": "2.15",
                "draw": "3.10",
                "lose": "3.30",
                "timestamp": datetime(2026, 6, 15, 9, 0, tzinfo=UTC).isoformat(),
            },
        )

        self.assertEqual(update.match_id, "wc2026_can_bih")
        self.assertEqual(update.market, "handicap_win_draw_win")
        self.assertEqual(update.handicap, 0.0)
        self.assertEqual(
            {selection.outcome for selection in update.selections},
            {"home_win", "draw", "away_win"},
        )

    def test_transformer_rejects_unknown_mapping(self) -> None:
        with self.assertRaises(TransformError) as error:
            self._transformer().transform_schedule_record(
                "provider-a",
                {"matchId": "missing", "status": "scheduled"},
            )

        self.assertEqual(error.exception.code, "match_id_mapping_not_found")

    def test_fetcher_publishes_with_match_id_partition_key(self) -> None:
        publisher = FakePublisher()
        service = ExternalFetcherService(
            config=ExternalFetcherConfig(
                provider="provider-a",
                odds_url="https://provider.test/odds",
            ),
            publisher=publisher,
            transformer=self._transformer(),
        )
        service._client = FakeClient(
            {
                "odds": [
                    {
                        "matchId": "ext-1",
                        "market": "spf",
                        "win": 2.2,
                        "draw": 3.1,
                        "lose": 3.4,
                    }
                ]
            }
        )

        count = asyncio.run(service.sync_odds())

        self.assertEqual(count, 1)
        self.assertEqual(publisher.messages[0]["topic"], EXTERNAL_ODDS_TOPIC)
        self.assertEqual(publisher.messages[0]["partition_key"], "wc2026_can_bih")

    def test_fetcher_publishes_schedule_topic(self) -> None:
        publisher = FakePublisher()
        service = ExternalFetcherService(
            config=ExternalFetcherConfig(
                provider="provider-a",
                schedule_url="https://provider.test/schedule",
            ),
            publisher=publisher,
            transformer=self._transformer(),
        )
        service._client = FakeClient(
            {
                "matches": [
                    {
                        "matchId": "ext-1",
                        "status": "scheduled",
                        "kickoffTimeUtc": "2026-06-12T19:00:00Z",
                    }
                ]
            }
        )

        count = asyncio.run(service.sync_schedule())

        self.assertEqual(count, 1)
        self.assertEqual(publisher.messages[0]["topic"], EXTERNAL_SCHEDULE_TOPIC)
        self.assertEqual(publisher.messages[0]["partition_key"], "wc2026_can_bih")

    def test_sporttery_nested_payload_is_normalized(self) -> None:
        mapper = StaticExternalMatchIdMapper()
        mapper.add("sporttery", "2040174", "wc2026_esp_cvi")
        transformer = ExternalDataTransformer(mapper)
        payload = {
            "errorCode": "0",
            "value": {
                "matchInfoList": [
                    {
                        "businessDate": "2026-06-15",
                        "subMatchList": [
                            {
                                "matchId": 2040174,
                                "matchStatus": "Selling",
                                "matchDate": "2026-06-16",
                                "matchTime": "00:00",
                                "matchNumStr": "Mon013",
                                "oddsList": [
                                    {
                                        "poolCode": "HAD",
                                        "h": "1.16",
                                        "d": "5.80",
                                        "a": "9.50",
                                        "updateDate": "2026-06-15",
                                        "updateTime": "18:00:00",
                                    },
                                    {
                                        "poolCode": "HHAD",
                                        "goalLine": "-2.00",
                                        "h": "1.54",
                                        "d": "4.55",
                                        "a": "3.85",
                                        "updateDate": "2026-06-15",
                                        "updateTime": "18:00:00",
                                    },
                                ],
                            }
                        ],
                    }
                ]
            },
        }

        schedule_updates = transformer.transform_schedule_payload("sporttery", payload)
        odds_updates = transformer.transform_odds_payload("sporttery", payload)

        self.assertEqual(schedule_updates[0].match_id, "wc2026_esp_cvi")
        self.assertEqual(schedule_updates[0].status, "scheduled")
        self.assertEqual(schedule_updates[0].kickoff_time_utc.isoformat(), "2026-06-15T16:00:00+00:00")
        self.assertEqual(len(odds_updates), 2)
        self.assertEqual(
            {update.market for update in odds_updates},
            {"win_draw_win", "handicap_win_draw_win"},
        )

    def test_espn_scoreboard_event_is_normalized(self) -> None:
        mapper = StaticExternalMatchIdMapper()
        mapper.add("espn", "760416", "wc2026_can_bih")
        transformer = ExternalDataTransformer(mapper)
        payload = {
            "events": [
                {
                    "id": "760416",
                    "date": "2026-06-12T19:00Z",
                    "competitions": [
                        {
                            "status": {"type": {"name": "STATUS_FULL_TIME"}},
                            "competitors": [
                                {"homeAway": "home", "score": "1"},
                                {"homeAway": "away", "score": "0"},
                            ],
                        }
                    ],
                }
            ]
        }

        updates = transformer.transform_schedule_payload("espn", payload)

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].match_id, "wc2026_can_bih")
        self.assertEqual(updates[0].status, "finished")
        self.assertEqual(updates[0].home_score, 1)
        self.assertEqual(updates[0].away_score, 0)

    def test_default_mapper_contains_seeded_espn_worldcup_matches(self) -> None:
        mapper = StaticExternalMatchIdMapper.from_env()

        self.assertEqual(
            DEFAULT_EXTERNAL_MATCH_ID_MAP["espn"]["760431"],
            "wc2026_aut_jor",
        )
        self.assertEqual(mapper.resolve_match_id("espn", "760435"), "wc2026_por_cod")
        self.assertEqual(mapper.resolve_match_id("ESPN", "760437"), "wc2026_eng_cro")
        self.assertEqual(mapper.resolve_match_id("espn", "760434"), "wc2026_gha_pan")
        self.assertEqual(mapper.resolve_match_id("espn", "760436"), "wc2026_uzb_col")

    def test_default_mapper_normalizes_june_17_espn_schedule_payload(self) -> None:
        transformer = ExternalDataTransformer(StaticExternalMatchIdMapper.from_env())
        payload = {
            "events": [
                {
                    "id": "760431",
                    "date": "2026-06-17T04:00Z",
                    "competitions": [
                        {
                            "status": {"type": {"name": "STATUS_SCHEDULED"}},
                            "competitors": [
                                {"homeAway": "home", "score": "0"},
                                {"homeAway": "away", "score": "0"},
                            ],
                        }
                    ],
                },
                {
                    "id": "760436",
                    "date": "2026-06-18T02:00Z",
                    "competitions": [
                        {
                            "status": {"type": {"name": "STATUS_SCHEDULED"}},
                            "competitors": [
                                {"homeAway": "home", "score": "0"},
                                {"homeAway": "away", "score": "0"},
                            ],
                        }
                    ],
                },
            ]
        }

        updates = transformer.transform_schedule_payload("espn", payload)

        self.assertEqual(
            [update.match_id for update in updates],
            ["wc2026_aut_jor", "wc2026_uzb_col"],
        )
        self.assertEqual([update.status for update in updates], ["scheduled", "scheduled"])
        self.assertIsNone(updates[0].home_score)
        self.assertIsNone(updates[1].away_score)


if __name__ == "__main__":
    unittest.main()
