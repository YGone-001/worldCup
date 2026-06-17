import unittest

from packages.engine.worldcup_engine.worldcup_progress import WorldCupProgressProvider


class WorldCupProgressTest(unittest.TestCase):
    def test_provider_lists_seeded_worldcup_matches(self) -> None:
        provider = WorldCupProgressProvider()
        matches = provider.list_matches()

        self.assertGreaterEqual(len(matches), 4)
        self.assertEqual(matches[0].match_id, "wc2026_mex_rsa")

    def test_finished_match_lottery_analysis_is_settled(self) -> None:
        provider = WorldCupProgressProvider()
        analysis = provider.analyze_lottery("wc2026_mex_rsa", None)

        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(analysis.settlement_status, "settled")
        home_win = next(item for item in analysis.outcomes if item.code == "home_win")
        self.assertEqual(home_win.probability, 0.999)

    def test_scheduled_match_lottery_analysis_is_open(self) -> None:
        provider = WorldCupProgressProvider()
        analysis = provider.analyze_lottery("wc2026_usa_par", None)

        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(analysis.settlement_status, "open")
        total = sum(item.probability for item in analysis.outcomes)
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_provider_includes_june_17_scoreboard_matches(self) -> None:
        provider = WorldCupProgressProvider()
        match_ids = {match.match_id for match in provider.list_matches()}

        self.assertIn("wc2026_aut_jor", match_ids)
        self.assertIn("wc2026_por_cod", match_ids)
        self.assertIn("wc2026_eng_cro", match_ids)
        self.assertIn("wc2026_gha_pan", match_ids)
        self.assertIn("wc2026_uzb_col", match_ids)


if __name__ == "__main__":
    unittest.main()
