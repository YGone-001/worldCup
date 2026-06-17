from packages.domain.worldcup_domain.schemas import ModelContribution


class PredictionAggregator:
    def normalize(self, home_win: float, draw: float, away_win: float) -> tuple[float, float, float]:
        values = [max(0.001, home_win), max(0.001, draw), max(0.001, away_win)]
        total = sum(values)
        return values[0] / total, values[1] / total, values[2] / total

    def confidence(self, event_count_signal: float, degradation_level: int) -> float:
        base = min(0.92, 0.62 + event_count_signal)
        penalty = min(0.5, degradation_level * 0.12)
        return round(max(0.1, base - penalty), 4)

    def default_models(self) -> list[ModelContribution]:
        return [
            ModelContribution(model_name="dynamic_elo", model_version="0.1.0", weight=0.25),
            ModelContribution(model_name="in_play_markov", model_version="0.1.0", weight=0.45),
            ModelContribution(model_name="bivariate_poisson", model_version="0.1.0", weight=0.30),
        ]

