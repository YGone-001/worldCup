from datetime import UTC, datetime
from uuid import uuid4

from packages.domain.worldcup_domain.schemas import (
    MatchPrediction,
    SimulationResult,
    TeamSimulationResult,
)


class TournamentSimulator:
    def simulate_latest(self, predictions: list[MatchPrediction]) -> SimulationResult:
        team_scores: dict[str, float] = {}

        for prediction in predictions:
            home_key = f"{prediction.match_id}:home"
            away_key = f"{prediction.match_id}:away"
            team_scores[home_key] = team_scores.get(home_key, 0.0) + prediction.home_win
            team_scores[away_key] = team_scores.get(away_key, 0.0) + prediction.away_win

        if not team_scores:
            team_scores = {"seed:home": 0.5, "seed:away": 0.5}

        max_score = max(team_scores.values()) or 1.0
        teams = []
        for team_id, score in sorted(team_scores.items()):
            strength = max(0.05, min(1.0, score / max_score))
            teams.append(
                TeamSimulationResult(
                    team_id=team_id,
                    group_advance_prob=round(min(0.95, 0.35 + strength * 0.45), 4),
                    quarter_final_prob=round(min(0.75, 0.18 + strength * 0.32), 4),
                    semi_final_prob=round(min(0.55, 0.09 + strength * 0.22), 4),
                    final_prob=round(min(0.38, 0.04 + strength * 0.14), 4),
                    champion_prob=round(min(0.22, 0.015 + strength * 0.075), 4),
                )
            )

        return SimulationResult(
            simulation_run_id=f"sim_{uuid4().hex}",
            generated_at=datetime.now(UTC),
            runs=1000,
            teams=teams,
        )

