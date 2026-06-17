from datetime import UTC, datetime
import unittest

from packages.domain.worldcup_domain.schemas import StandardEvent
from packages.engine.worldcup_engine.aggregator import PredictionAggregator
from packages.engine.worldcup_engine.predictor import BaselinePredictionEngine
from packages.engine.worldcup_engine.storage import InMemoryPredictionStore


class PredictionEngineTest(unittest.TestCase):
    def test_goal_event_moves_probability(self) -> None:
        store = InMemoryPredictionStore()
        engine = BaselinePredictionEngine(PredictionAggregator())

        initial_event = StandardEvent(
            event_id="evt_1",
            match_id="match_1",
            event_type="match_started",
            event_time=datetime.now(UTC),
            match_clock_sec=0,
        )
        initial_prediction = engine.predict(store.apply_event(initial_event))

        goal_event = StandardEvent(
            event_id="evt_2",
            match_id="match_1",
            event_type="goal",
            event_time=datetime.now(UTC),
            team_id="home",
            match_clock_sec=1800,
        )
        goal_prediction = engine.predict(store.apply_event(goal_event))

        self.assertGreater(goal_prediction.home_win, initial_prediction.home_win)
        self.assertAlmostEqual(
            goal_prediction.home_win + goal_prediction.draw + goal_prediction.away_win,
            1.0,
            places=3,
        )

    def test_goal_projection_increases_with_attacking_pressure(self) -> None:
        store = InMemoryPredictionStore()
        engine = BaselinePredictionEngine(PredictionAggregator())

        initial_event = StandardEvent(
            event_id="evt_goal_projection_1",
            match_id="match_goal_projection_1",
            event_type="match_started",
            event_time=datetime.now(UTC),
            match_clock_sec=0,
        )
        initial_prediction = engine.predict(store.apply_event(initial_event))

        for index in range(5):
            store.apply_event(
                StandardEvent(
                    event_id=f"evt_goal_projection_shot_{index}",
                    match_id="match_goal_projection_1",
                    event_type="shot",
                    event_time=datetime.now(UTC),
                    team_id="home",
                    match_clock_sec=900 + index * 60,
                    payload={"side": "home", "xg": 0.18},
                )
            )
        pressure_prediction = engine.predict(store.get_state("match_goal_projection_1"))

        self.assertGreater(
            pressure_prediction.expected_total_goals,
            initial_prediction.expected_total_goals,
        )
        self.assertAlmostEqual(
            pressure_prediction.over_2_5_goals + pressure_prediction.under_2_5_goals,
            1.0,
            places=3,
        )

    def test_finished_match_prediction_is_settled(self) -> None:
        store = InMemoryPredictionStore()
        engine = BaselinePredictionEngine(PredictionAggregator())

        events = [
            StandardEvent(
                event_id="evt_settled_start",
                match_id="match_settled_1",
                event_type="match_started",
                event_time=datetime.now(UTC),
                match_clock_sec=0,
            ),
            StandardEvent(
                event_id="evt_settled_goal_1",
                match_id="match_settled_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="home",
                match_clock_sec=1200,
                payload={"side": "home"},
            ),
            StandardEvent(
                event_id="evt_settled_goal_2",
                match_id="match_settled_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="away",
                match_clock_sec=4100,
                payload={"side": "away"},
            ),
            StandardEvent(
                event_id="evt_settled_goal_3",
                match_id="match_settled_1",
                event_type="goal",
                event_time=datetime.now(UTC),
                team_id="home",
                match_clock_sec=5000,
                payload={"side": "home"},
            ),
            StandardEvent(
                event_id="evt_settled_finish",
                match_id="match_settled_1",
                event_type="match_finished",
                event_time=datetime.now(UTC),
                match_clock_sec=5400,
            ),
        ]

        state = None
        for event in events:
            state = store.apply_event(event)

        assert state is not None
        prediction = engine.predict(state)

        self.assertEqual(prediction.home_win, 1.0)
        self.assertEqual(prediction.draw, 0.0)
        self.assertEqual(prediction.away_win, 0.0)
        self.assertEqual(prediction.expected_total_goals, 3.0)
        self.assertEqual(prediction.over_2_5_goals, 1.0)

    def test_goal_projection_calibration_updates_future_totals(self) -> None:
        engine = BaselinePredictionEngine(PredictionAggregator())
        state = InMemoryPredictionStore().apply_event(
            StandardEvent(
                event_id="evt_calibration_start_1",
                match_id="match_calibration_1",
                event_type="match_started",
                event_time=datetime.now(UTC),
                match_clock_sec=0,
            )
        )
        before = engine.predict(state)

        snapshot = engine.calibrate_total_goals(
            match_id="match_calibration_1",
            predicted_total_goals=before.expected_total_goals,
            actual_total_goals=0,
        )
        after = engine.predict(state)

        self.assertEqual(snapshot.sample_count, 1)
        self.assertLess(snapshot.total_goals_factor, 1.0)
        self.assertLess(after.expected_total_goals, before.expected_total_goals)


if __name__ == "__main__":
    unittest.main()
