# 2026 World Cup Prediction Engine

This repository contains the first runnable scaffold for the 2026 World Cup intelligent prediction engine.

The current implementation is a minimum development loop:

- FastAPI prediction API.
- Standard event schema.
- In-memory match state store.
- Local JSONL event bus for development-time event replay and auditing.
- Data quality scoring for duplicate, delayed and incomplete events.
- Baseline live prediction engine.
- Tournament simulation placeholder.
- WebSocket prediction subscription.
- Browser-served Web UI console.
- World Cup match progress provider with match selection in the Web UI.
- Sports-lottery style win/draw/loss probability analysis with fair decimal odds.
- Online expected-goals calibration from post-match total-goals error.
- Optional Kafka/Redpanda event bus with async consumer workflow.
- Optional external schedule and lottery odds anti-corruption layer.
- Docker Compose infrastructure blueprint for PostgreSQL, Redis, Redpanda and ClickHouse.

## Goal Projection Calibration

The baseline model keeps a lightweight in-memory calibration state for `expected_total_goals`.
When a `match_finished` event is accepted, the runtime compares the latest pre-finish
prediction with the actual final total goals and updates a bounded calibration factor and bias.
Future live predictions use that calibration before producing `expected_total_goals`,
`over_2_5_goals` and `under_2_5_goals`.

This is intentionally online and conservative: settled predictions still report the actual final
score, while calibration learns only from the last live prediction that existed before the finish
event.

## Repository Layout

```text
apps/
  api/
    worldcup_api/
      main.py
      runtime.py
  web/
    index.html
    static/
      app.js
      styles.css
packages/
  domain/
    worldcup_domain/
      schemas.py
  engine/
    worldcup_engine/
      aggregator.py
      predictor.py
      quality.py
      simulation.py
      storage.py
infra/
  docker-compose.yml
  postgres/init.sql
  clickhouse/init.sql
docs/
  architecture-design.md
  implementation-plan.md
tests/
  test_prediction_engine.py
```

## Local Development

Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run tests:

```powershell
python -m unittest discover -s tests
```

Start the API:

```powershell
uvicorn apps.api.worldcup_api.main:app --reload --host 0.0.0.0 --port 8000
```

Open the Web UI:

```text
http://localhost:8000/
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Ingest a sample event:

```powershell
$body = Get-Content .\examples\shot-event.json -Raw
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8000/api/v1/events `
  -ContentType "application/json" `
  -Body $body
```

Query prediction:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/matches/match_001/prediction
```

Query match state:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/matches/match_001/state
```

Query prediction evaluation:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/matches/wc2026_mex_rsa/evaluation
```

Query date-scoped prediction backtest:

```powershell
Invoke-RestMethod `
  "http://localhost:8000/api/v1/predictions/backtest?date_from=2026-06-11&date_to=2026-06-17"
```

Query goal projection calibration status:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/models/goal-calibration
```

Query World Cup match progress:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/worldcup/matches
```

Query sports-lottery style probability analysis:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/matches/wc2026_usa_par/lottery-analysis
```

Query runtime status:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/runtime/status
```

Query latest simulation:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/tournament/simulation/latest
```

## Infrastructure

The infrastructure blueprint is under `infra/docker-compose.yml`.

The current machine does not have Docker available in PATH. After Docker is installed, run:

```powershell
docker compose -f infra/docker-compose.yml up -d
```

## Kafka Mode

The default local mode uses JSONL files and does not require Kafka.

Enable Kafka/Redpanda mode:

```powershell
docker compose -f infra/docker-compose.yml up -d redpanda
$env:WORLDCUP_EVENT_BUS="kafka"
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:19092"
$env:WORLDCUP_KAFKA_RAW_TOPIC="worldcup.events.raw"
$env:WORLDCUP_KAFKA_PREDICTION_TOPIC="worldcup.predictions.updated"
uvicorn apps.api.worldcup_api.main:app --reload --host 0.0.0.0 --port 8000
```

Kafka mode uses:

```text
worldcup.events.raw
worldcup.predictions.updated
```

The raw event producer uses `match_id` as the Kafka message key so all events for the same match stay in partition order. The consumer checks `event_id` before recomputing predictions to block duplicate at-least-once deliveries.

## External Data Fetcher

The external fetcher is disabled by default and only starts in Kafka mode.

```powershell
$env:WORLDCUP_EVENT_BUS="kafka"
$env:WORLDCUP_EXTERNAL_FETCHER_ENABLED="true"
$env:WORLDCUP_SCHEDULE_PROVIDER="espn"
$env:WORLDCUP_ODDS_PROVIDER="sporttery"
$env:WORLDCUP_SCHEDULE_API_URL="https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260719"
$env:WORLDCUP_ODDS_API_URL="https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry?clientCode=3001"
$env:WORLDCUP_EXTERNAL_MATCH_ID_MAP='{"espn":{"760415":"wc2026_mex_rsa"},"sporttery":{"2040174":"your_internal_match_id"}}'
```

Normalized external messages are published with `match_id` as the Kafka key:

```text
worldcup.schedule.external
worldcup.odds.external
```

## Next Engineering Steps

1. Add live Redpanda integration tests and topic initialization scripts.
2. Replace in-memory storage with Redis and PostgreSQL adapters.
3. Move feature updates into a stream worker.
4. Add real model artifacts and a model registry.
5. Add provider connectors for Sportradar, Opta, weather and odds feeds.
6. Add load tests for API and WebSocket push paths.
