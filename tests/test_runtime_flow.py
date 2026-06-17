from datetime import UTC, date, datetime
import asyncio
import shutil
import unittest

from apps.api.worldcup_api.runtime import Runtime
from packages.domain.worldcup_domain.schemas import MatchPrediction, StandardEvent


class RuntimeFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree("data", ignore_errors=True)

    def test_runtime_records_event_quality_and_bus_messages(self) -> None:
        runtime = Runtime()
        event = StandardEvent(
            event_id="evt_runtime_1",
            match_id="match_runtime_1",
            event_type="shot",
            event_time=datetime.now(UTC),
            team_id="home",
            match_clock_sec=120,
            payload={"xg": 0.11, "side": "home"},
        )

        prediction, quality = asyncio.run(runtime.ingest_event(event))
        status = runtime.get_status()
        recent_events = runtime.list_recent_events()
        prediction_history = runtime.list_prediction_history("match_runtime_1")

        self.assertTrue(quality.accepted)
        self.assertIsNotNone(prediction)
        assert prediction is not None
        self.assertEqual(prediction.match_id, "match_runtime_1")
        self.assertEqual(status.event_count, 1)
        self.assertEqual(status.prediction_count, 1)
        self.assertEqual(status.bus_message_count, 2)
        self.assertEqual(len(recent_events), 1)
        self.assertEqual(recent_events[0].event_id, "evt_runtime_1")
        self.assertEqual(len(prediction_history), 1)

    def test_duplicate_event_is_not_republished(self) -> None:
        runtime = Runtime()
        event = StandardEvent(
            event_id="evt_duplicate_1",
            match_id="match_duplicate_1",
            event_type="goal",
            event_time=datetime.now(UTC),
            team_id="home",
            match_clock_sec=600,
            payload={"side": "home"},
        )

        asyncio.run(runtime.ingest_event(event))
        _, quality = asyncio.run(runtime.ingest_event(event))
        status = runtime.get_status()
        recent_events = runtime.list_recent_events()

        self.assertFalse(quality.accepted)
        self.assertIn("duplicate_event", quality.warnings)
        self.assertEqual(status.event_count, 1)
        self.assertEqual(status.prediction_count, 1)
        self.assertEqual(status.bus_message_count, 2)
        self.assertEqual(len(recent_events), 2)
        self.assertFalse(recent_events[0].accepted)

    def test_finished_match_evaluation_compares_prediction_to_actual_score(self) -> None:
        runtime = Runtime()
        events = [
            StandardEvent(
                event_id="evt_eval_start",
                match_id="match_eval_1",
                event_type="match_started",
                event_time=datetime.now(UTC),
                match_clock_sec=0,
            ),
            StandardEvent(
                event_id="evt_eval_home_goal",
                match_id="match_eval_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="home",
                match_clock_sec=1600,
                payload={"side": "home"},
            ),
            StandardEvent(
                event_id="evt_eval_finish",
                match_id="match_eval_1",
                event_type="match_finished",
                event_time=datetime.now(UTC),
                match_clock_sec=5400,
            ),
        ]

        for event in events:
            asyncio.run(runtime.ingest_event(event))

        evaluation = runtime.get_prediction_evaluation("match_eval_1")

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation.status, "settled")
        self.assertEqual(evaluation.actual_total_goals, 1)
        self.assertEqual(evaluation.predicted_total_goals, 1.0)
        self.assertEqual(evaluation.total_goals_error, 0.0)
        self.assertTrue(evaluation.outcome_hit)

    def test_prediction_evaluation_includes_over_under_result(self) -> None:
        runtime = Runtime()
        events = [
            StandardEvent(
                event_id="evt_over_start",
                match_id="match_over_1",
                event_type="match_started",
                event_time=datetime.now(UTC),
                match_clock_sec=0,
            ),
            StandardEvent(
                event_id="evt_over_home_goal_1",
                match_id="match_over_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="home",
                match_clock_sec=900,
                payload={"side": "home"},
            ),
            StandardEvent(
                event_id="evt_over_home_goal_2",
                match_id="match_over_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="home",
                match_clock_sec=1800,
                payload={"side": "home"},
            ),
            StandardEvent(
                event_id="evt_over_away_goal",
                match_id="match_over_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="away",
                match_clock_sec=2700,
                payload={"side": "away"},
            ),
            StandardEvent(
                event_id="evt_over_finish",
                match_id="match_over_1",
                event_type="match_finished",
                event_time=datetime.now(UTC),
                match_clock_sec=5400,
            ),
        ]

        for event in events:
            asyncio.run(runtime.ingest_event(event))

        evaluation = runtime.get_prediction_evaluation("match_over_1")

        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertTrue(evaluation.actual_over_2_5_goals)
        self.assertTrue(evaluation.predicted_over_2_5_goals)
        self.assertTrue(evaluation.over_2_5_hit)

    def test_prediction_backtest_groups_metrics_by_match_date(self) -> None:
        runtime = Runtime()
        self._save_prediction(
            runtime,
            match_id="wc2026_mex_rsa",
            home_win=0.5,
            draw=0.3,
            away_win=0.2,
            expected_total_goals=2.6,
            over_2_5_goals=0.55,
        )
        self._save_prediction(
            runtime,
            match_id="wc2026_kor_cze",
            home_win=0.6,
            draw=0.2,
            away_win=0.2,
            expected_total_goals=2.4,
            over_2_5_goals=0.7,
        )

        report = runtime.get_prediction_backtest(
            date_from=date(2026, 6, 11),
            date_to=date(2026, 6, 11),
        )

        self.assertEqual(report.match_count, 2)
        self.assertEqual(report.settled_count, 2)
        self.assertEqual(report.pending_count, 0)
        self.assertEqual(report.evaluated_count, 2)
        self.assertEqual(report.average_brier_score, 0.31)
        self.assertEqual(report.total_goals_mae, 0.6)
        self.assertEqual(report.over_2_5_hit_rate, 0.5)
        self.assertEqual(len(report.buckets), 1)
        self.assertEqual(report.buckets[0].date, date(2026, 6, 11))
        self.assertEqual(report.buckets[0].average_brier_score, 0.31)
        self.assertEqual(report.buckets[0].total_goals_mae, 0.6)
        self.assertEqual(report.buckets[0].over_2_5_hit_rate, 0.5)

    def test_match_finished_event_updates_goal_calibration(self) -> None:
        runtime = Runtime()
        initial_event = StandardEvent(
            event_id="evt_calibrate_runtime_start",
            match_id="match_calibrate_runtime_1",
            event_type="match_started",
            event_time=datetime.now(UTC),
            match_clock_sec=0,
        )
        finish_event = StandardEvent(
            event_id="evt_calibrate_runtime_finish",
            match_id="match_calibrate_runtime_1",
            event_type="match_finished",
            event_time=datetime.now(UTC),
            match_clock_sec=5400,
        )

        initial_prediction, _ = asyncio.run(runtime.ingest_event(initial_event))
        before = runtime.get_goal_calibration()
        final_prediction, _ = asyncio.run(runtime.ingest_event(finish_event))
        after = runtime.get_goal_calibration()

        self.assertIsNotNone(initial_prediction)
        self.assertIsNotNone(final_prediction)
        self.assertEqual(before.sample_count, 0)
        self.assertEqual(after.sample_count, 1)
        self.assertEqual(after.last_match_id, "match_calibrate_runtime_1")
        self.assertLess(after.total_goals_factor, before.total_goals_factor)
        assert final_prediction is not None
        self.assertEqual(final_prediction.expected_total_goals, 0.0)

    def _save_prediction(
        self,
        runtime: Runtime,
        match_id: str,
        home_win: float,
        draw: float,
        away_win: float,
        expected_total_goals: float,
        over_2_5_goals: float,
    ) -> None:
        runtime.store.save_prediction(
            MatchPrediction(
                prediction_id=f"pred_{match_id}",
                prediction_version_id=f"pv_{match_id}",
                match_id=match_id,
                generated_at=datetime.now(UTC),
                feature_version=f"fv_{match_id}_test",
                models=[],
                home_win=home_win,
                draw=draw,
                away_win=away_win,
                expected_home_goals=expected_total_goals / 2,
                expected_away_goals=expected_total_goals / 2,
                expected_total_goals=expected_total_goals,
                over_2_5_goals=over_2_5_goals,
                under_2_5_goals=1.0 - over_2_5_goals,
                confidence_level=0.72,
                degradation_level=0,
            )
        )


if __name__ == "__main__":
    unittest.main()
