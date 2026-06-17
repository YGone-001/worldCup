from datetime import UTC, datetime

from packages.domain.worldcup_domain.schemas import (
    LotteryAnalysis,
    LotteryOutcome,
    MatchPrediction,
    WorldCupMatch,
)


class WorldCupProgressProvider:
    def __init__(self) -> None:
        self.matches = self._seed_matches()

    def list_matches(self) -> list[WorldCupMatch]:
        return sorted(self.matches, key=lambda match: (match.kickoff_time_utc, match.match_no))

    def get_match(self, match_id: str) -> WorldCupMatch | None:
        for match in self.matches:
            if match.match_id == match_id:
                return match
        return None

    def analyze_lottery(
        self,
        match_id: str,
        prediction: MatchPrediction | None,
    ) -> LotteryAnalysis | None:
        match = self.get_match(match_id)
        if match is None:
            return None

        if prediction is not None:
            probabilities = {
                "home_win": prediction.home_win,
                "draw": prediction.draw,
                "away_win": prediction.away_win,
            }
            confidence = prediction.confidence_level
            source_prediction_version_id = prediction.prediction_version_id
        else:
            probabilities = self._baseline_probabilities(match)
            confidence = 0.58 if match.status != "finished" else 1.0
            source_prediction_version_id = None

        if match.status == "finished" and match.home_score is not None and match.away_score is not None:
            probabilities = self._settled_probabilities(match.home_score, match.away_score)
            confidence = 1.0

        outcomes = [
            self._outcome("home_win", "home_win", probabilities["home_win"]),
            self._outcome("draw", "draw", probabilities["draw"]),
            self._outcome("away_win", "away_win", probabilities["away_win"]),
        ]

        return LotteryAnalysis(
            match=match,
            generated_at=datetime.now(UTC),
            source_prediction_version_id=source_prediction_version_id,
            outcomes=outcomes,
            confidence_level=round(confidence, 4),
            settlement_status="settled" if match.status == "finished" else "open",
            note="Probability analytics only. This is not a betting recommendation.",
        )

    def _outcome(self, code: str, label: str, probability: float) -> LotteryOutcome:
        safe_probability = max(0.001, min(0.999, probability))
        return LotteryOutcome(
            code=code,
            label=label,
            probability=round(safe_probability, 4),
            fair_decimal_odds=round(1.0 / safe_probability, 3),
        )

    def _baseline_probabilities(self, match: WorldCupMatch) -> dict[str, float]:
        seed_strength = {
            "mex": 0.58,
            "rsa": 0.42,
            "kor": 0.55,
            "cze": 0.49,
            "can": 0.54,
            "bih": 0.48,
            "usa": 0.62,
            "par": 0.47,
            "qat": 0.46,
            "sui": 0.57,
            "bra": 0.68,
            "mar": 0.58,
            "hai": 0.38,
            "sco": 0.52,
            "esp": 0.72,
            "cvi": 0.46,
            "aut": 0.59,
            "jor": 0.41,
            "por": 0.73,
            "cod": 0.48,
            "eng": 0.71,
            "cro": 0.63,
            "gha": 0.55,
            "pan": 0.46,
            "uzb": 0.49,
            "col": 0.64,
        }
        home_strength = seed_strength.get(match.home_team_id, 0.5) + 0.04
        away_strength = seed_strength.get(match.away_team_id, 0.5)
        delta = home_strength - away_strength
        draw = max(0.22, min(0.34, 0.29 - abs(delta) * 0.12))
        remaining = 1.0 - draw
        home_win = remaining * (0.5 + delta * 0.65)
        away_win = remaining - home_win
        total = home_win + draw + away_win
        return {
            "home_win": home_win / total,
            "draw": draw / total,
            "away_win": away_win / total,
        }

    def _settled_probabilities(self, home_score: int, away_score: int) -> dict[str, float]:
        return {
            "home_win": 1.0 if home_score > away_score else 0.0,
            "draw": 1.0 if home_score == away_score else 0.0,
            "away_win": 1.0 if away_score > home_score else 0.0,
        }

    def _seed_matches(self) -> list[WorldCupMatch]:
        source = "seeded-public-schedule-2026-06-12"
        return [
            WorldCupMatch(
                match_id="wc2026_mex_rsa",
                match_no=1,
                group="A",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 11, 19, 0, tzinfo=UTC),
                venue="Estadio Azteca",
                city="Mexico City",
                home_team_id="mex",
                home_team_name="Mexico",
                away_team_id="rsa",
                away_team_name="South Africa",
                status="finished",
                home_score=2,
                away_score=0,
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_kor_cze",
                match_no=2,
                group="A",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 11, 22, 0, tzinfo=UTC),
                venue="Estadio Akron",
                city="Guadalajara",
                home_team_id="kor",
                home_team_name="South Korea",
                away_team_id="cze",
                away_team_name="Czechia",
                status="finished",
                home_score=2,
                away_score=1,
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_can_bih",
                match_no=3,
                group="B",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 12, 19, 0, tzinfo=UTC),
                venue="BMO Field",
                city="Toronto",
                home_team_id="can",
                home_team_name="Canada",
                away_team_id="bih",
                away_team_name="Bosnia and Herzegovina",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_usa_par",
                match_no=4,
                group="D",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 13, 1, 0, tzinfo=UTC),
                venue="SoFi Stadium",
                city="Los Angeles",
                home_team_id="usa",
                home_team_name="United States",
                away_team_id="par",
                away_team_name="Paraguay",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_qat_sui",
                match_no=8,
                group="B",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 13, 19, 0, tzinfo=UTC),
                venue="Levi's Stadium",
                city="Santa Clara",
                home_team_id="qat",
                home_team_name="Qatar",
                away_team_id="sui",
                away_team_name="Switzerland",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_bra_mar",
                match_no=7,
                group="C",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 13, 22, 0, tzinfo=UTC),
                venue="MetLife Stadium",
                city="New York New Jersey",
                home_team_id="bra",
                home_team_name="Brazil",
                away_team_id="mar",
                away_team_name="Morocco",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_hai_sco",
                match_no=5,
                group="C",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 14, 1, 0, tzinfo=UTC),
                venue="Gillette Stadium",
                city="Boston",
                home_team_id="hai",
                home_team_name="Haiti",
                away_team_id="sco",
                away_team_name="Scotland",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_esp_cvi",
                match_no=13,
                group="H",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 15, 16, 0, tzinfo=UTC),
                venue="Mercedes-Benz Stadium",
                city="Atlanta",
                home_team_id="esp",
                home_team_name="Spain",
                away_team_id="cvi",
                away_team_name="Cape Verde",
                status="scheduled",
                source=source,
            ),
            WorldCupMatch(
                match_id="wc2026_aut_jor",
                match_no=21,
                group="J",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 17, 4, 0, tzinfo=UTC),
                venue="Levi's Stadium",
                city="Santa Clara",
                home_team_id="aut",
                home_team_name="Austria",
                away_team_id="jor",
                away_team_name="Jordan",
                status="scheduled",
                source="espn-scoreboard-2026-06-17",
            ),
            WorldCupMatch(
                match_id="wc2026_por_cod",
                match_no=22,
                group="K",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 17, 17, 0, tzinfo=UTC),
                venue="NRG Stadium",
                city="Houston",
                home_team_id="por",
                home_team_name="Portugal",
                away_team_id="cod",
                away_team_name="Congo DR",
                status="scheduled",
                source="espn-scoreboard-2026-06-17",
            ),
            WorldCupMatch(
                match_id="wc2026_eng_cro",
                match_no=23,
                group="L",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 17, 20, 0, tzinfo=UTC),
                venue="AT&T Stadium",
                city="Dallas",
                home_team_id="eng",
                home_team_name="England",
                away_team_id="cro",
                away_team_name="Croatia",
                status="scheduled",
                source="espn-scoreboard-2026-06-17",
            ),
            WorldCupMatch(
                match_id="wc2026_gha_pan",
                match_no=24,
                group="I",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 17, 23, 0, tzinfo=UTC),
                venue="BMO Field",
                city="Toronto",
                home_team_id="gha",
                home_team_name="Ghana",
                away_team_id="pan",
                away_team_name="Panama",
                status="scheduled",
                source="espn-scoreboard-2026-06-17",
            ),
            WorldCupMatch(
                match_id="wc2026_uzb_col",
                match_no=25,
                group="K",
                stage="Group",
                kickoff_time_utc=datetime(2026, 6, 18, 2, 0, tzinfo=UTC),
                venue="Estadio Banorte",
                city="Mexico City",
                home_team_id="uzb",
                home_team_name="Uzbekistan",
                away_team_id="col",
                away_team_name="Colombia",
                status="scheduled",
                source="espn-scoreboard-2026-06-17",
            ),
        ]
