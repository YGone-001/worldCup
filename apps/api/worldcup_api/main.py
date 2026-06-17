from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.worldcup_api.runtime import Runtime
from packages.domain.worldcup_domain.schemas import (
    EventAuditRecord,
    EventIngestResponse,
    GoalCalibrationSnapshot,
    LotteryAnalysis,
    MatchPrediction,
    MatchState,
    PredictionBacktestReport,
    PredictionEvaluation,
    RuntimeStatus,
    SimulationResult,
    StandardEvent,
    WorldCupMatch,
)
from packages.engine.worldcup_engine.adapters.schemas import (
    ExternalOddsUpdate,
    ExternalScheduleUpdate,
)


runtime = Runtime()
WEB_ROOT = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(
    title="World Cup Prediction Engine",
    version="0.1.0",
    description="Basic runtime for live football prediction workflows.",
)
app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")


@app.get("/", response_class=FileResponse)
def web_console() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def startup() -> None:
    await runtime.startup()


@app.on_event("shutdown")
async def shutdown() -> None:
    await runtime.shutdown()


@app.get("/api/v1/runtime/status", response_model=RuntimeStatus)
def get_runtime_status() -> RuntimeStatus:
    return runtime.get_status()


@app.get("/api/v1/models/goal-calibration", response_model=GoalCalibrationSnapshot)
def get_goal_calibration() -> GoalCalibrationSnapshot:
    return runtime.get_goal_calibration()


@app.get("/api/v1/worldcup/matches", response_model=list[WorldCupMatch])
def list_worldcup_matches() -> list[WorldCupMatch]:
    return runtime.list_worldcup_matches()


@app.post("/api/v1/external/refresh")
async def refresh_external_data() -> dict[str, int]:
    return await runtime.refresh_external_data()


@app.get("/api/v1/external/matches", response_model=list[ExternalScheduleUpdate])
def list_external_matches() -> list[ExternalScheduleUpdate]:
    return runtime.list_external_schedule_updates()


@app.get("/api/v1/external/odds", response_model=list[ExternalOddsUpdate])
def list_external_odds(match_id: str | None = None) -> list[ExternalOddsUpdate]:
    return runtime.list_external_odds_updates(match_id)


@app.post("/api/v1/events", response_model=EventIngestResponse)
async def ingest_event(event: StandardEvent) -> EventIngestResponse:
    prediction, quality = await runtime.ingest_event(event)
    if quality.accepted and prediction is not None:
        await runtime.broadcast_prediction(prediction)
    return EventIngestResponse(
        accepted=quality.accepted,
        event_id=event.event_id,
        match_id=event.match_id,
        data_quality=quality,
        prediction=prediction,
    )


@app.get("/api/v1/events/recent", response_model=list[EventAuditRecord])
def list_recent_events(limit: int = Query(default=20, ge=1, le=100)) -> list[EventAuditRecord]:
    return runtime.list_recent_events(limit)


@app.get("/api/v1/matches/{match_id}/prediction", response_model=MatchPrediction)
def get_match_prediction(match_id: str) -> MatchPrediction:
    prediction = runtime.get_prediction(match_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="prediction_not_found")
    return prediction


@app.get("/api/v1/matches/{match_id}/lottery-analysis", response_model=LotteryAnalysis)
def get_lottery_analysis(match_id: str) -> LotteryAnalysis:
    analysis = runtime.get_lottery_analysis(match_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="match_not_found")
    return analysis


@app.get("/api/v1/matches/{match_id}/predictions/recent", response_model=list[MatchPrediction])
def list_recent_match_predictions(
    match_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[MatchPrediction]:
    return runtime.list_prediction_history(match_id, limit)


@app.get("/api/v1/matches/{match_id}/state", response_model=MatchState)
def get_match_state(match_id: str) -> MatchState:
    state = runtime.get_state(match_id)
    if state is None:
        raise HTTPException(status_code=404, detail="state_not_found")
    return state


@app.get("/api/v1/matches/{match_id}/evaluation", response_model=PredictionEvaluation)
def get_match_evaluation(match_id: str) -> PredictionEvaluation:
    evaluation = runtime.get_prediction_evaluation(match_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="state_not_found")
    return evaluation


@app.get("/api/v1/predictions/backtest", response_model=PredictionBacktestReport)
def get_prediction_backtest(
    date_from: date | None = None,
    date_to: date | None = None,
) -> PredictionBacktestReport:
    return runtime.get_prediction_backtest(date_from=date_from, date_to=date_to)


@app.get("/api/v1/tournament/simulation/latest", response_model=SimulationResult)
def get_latest_simulation() -> SimulationResult:
    return runtime.get_latest_simulation()


@app.websocket("/api/v1/ws/predictions")
async def prediction_ws(websocket: WebSocket) -> None:
    await runtime.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await runtime.handle_subscription(websocket, message)
    except WebSocketDisconnect:
        runtime.disconnect(websocket)
