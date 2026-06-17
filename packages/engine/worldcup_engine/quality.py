from datetime import UTC, datetime

from packages.domain.worldcup_domain.schemas import DataQualityResult, StandardEvent


class DataQualityService:
    def inspect(self, event: StandardEvent, duplicate: bool) -> DataQualityResult:
        warnings: list[str] = []
        score = event.confidence_score

        if duplicate and not event.correction_flag:
            warnings.append("duplicate_event")
            score *= 0.5

        latency_ms = max(0.0, (event.ingest_time - event.event_time).total_seconds() * 1000.0)
        if latency_ms > 10000:
            warnings.append("high_ingest_latency")
            score *= 0.9

        future_skew_sec = (event.event_time - datetime.now(UTC)).total_seconds()
        if future_skew_sec > 21600:
            warnings.append("event_time_future_skew")
            score *= 0.85

        if event.event_type in {"goal", "shot", "xg_update"} and not event.team_id:
            warnings.append("missing_team_id")
            score *= 0.8

        if event.event_type == "shot" and "xg" not in event.payload:
            warnings.append("missing_xg_estimate")
            score *= 0.92

        accepted = not duplicate or event.correction_flag
        return DataQualityResult(
            accepted=accepted,
            score=round(max(0.0, min(1.0, score)), 4),
            warnings=warnings,
            ingest_latency_ms=round(latency_ms, 3),
        )

