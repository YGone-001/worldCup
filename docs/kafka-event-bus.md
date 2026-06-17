# Kafka/Redpanda Event Bus Implementation

## 1. Goal

This document describes the Kafka/Redpanda event bus implementation for the 2026 World Cup prediction engine.

The implementation keeps the existing `JsonlEventBus` for local development and adds a Kafka-backed path for asynchronous decoupling.

## 2. New Components

### 2.1 KafkaEventBus

File:

```text
packages/engine/worldcup_engine/event_bus_kafka.py
```

Responsibilities:

- Connect to Kafka or Redpanda with `aiokafka`.
- Publish raw match events.
- Use `match_id` as Kafka message key.
- Publish JSON payloads to downstream topics.
- Disconnect gracefully during application shutdown.

Important ordering rule:

```text
Kafka message key = event.match_id
```

This keeps all events for the same match in the same Kafka partition, preserving per-match event order during parallel consumption.

### 2.2 KafkaPredictionConsumerWorker

File:

```text
packages/engine/worldcup_engine/consumer_worker.py
```

Responsibilities:

- Subscribe to `worldcup.events.raw`.
- Decode Kafka messages into `StandardEvent`.
- Reject duplicate event delivery by `event_id`.
- Update match state.
- Recompute prediction.
- Build sports-lottery style probability output.
- Publish updated prediction payload to `worldcup.predictions.updated`.
- Broadcast prediction updates to WebSocket subscribers.

Idempotency rule:

```text
if event_id already exists in store:
    skip recomputation
    append audit record with duplicate_event
```

This protects the prediction engine from Kafka at-least-once delivery duplicates.

## 3. Kafka Topics

| Topic | Direction | Description |
|---|---|---|
| worldcup.events.raw | API to consumer | Raw standard event stream |
| worldcup.predictions.updated | Consumer to downstream | Updated probability and fair odds result |

Topic names are configurable:

```text
WORLDCUP_KAFKA_RAW_TOPIC=worldcup.events.raw
WORLDCUP_KAFKA_PREDICTION_TOPIC=worldcup.predictions.updated
```

## 4. Enable Kafka Mode

Default mode remains JSONL:

```text
WORLDCUP_EVENT_BUS=jsonl
```

Enable Kafka mode:

```text
WORLDCUP_EVENT_BUS=kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:19092
WORLDCUP_KAFKA_RAW_TOPIC=worldcup.events.raw
WORLDCUP_KAFKA_PREDICTION_TOPIC=worldcup.predictions.updated
WORLDCUP_KAFKA_CONSUMER_GROUP=worldcup-prediction-engine
```

Start Redpanda:

```powershell
docker compose -f infra/docker-compose.yml up -d redpanda
```

Start API:

```powershell
$env:WORLDCUP_EVENT_BUS="kafka"
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:19092"
uvicorn apps.api.worldcup_api.main:app --reload --host 0.0.0.0 --port 8000
```

## 5. Runtime Lifecycle

FastAPI startup:

```text
runtime.startup()
  -> KafkaEventBus.connect()
  -> KafkaPredictionConsumerWorker.start()
```

FastAPI shutdown:

```text
runtime.shutdown()
  -> KafkaPredictionConsumerWorker.stop()
  -> KafkaEventBus.disconnect()
```

This gives the application a graceful shutdown path and avoids leaving Kafka producers or consumers open.

## 6. API Behavior

### JSONL mode

In JSONL mode, API requests are processed synchronously:

```text
POST /api/v1/events
  -> quality check
  -> state update
  -> prediction recompute
  -> JSONL event write
  -> response includes prediction
```

### Kafka mode

In Kafka mode, API requests only publish accepted raw events:

```text
POST /api/v1/events
  -> lightweight quality check
  -> publish to worldcup.events.raw with key=match_id
  -> consumer handles recompute asynchronously
```

The response may not include an immediate prediction in Kafka mode, because prediction recomputation is intentionally decoupled from the API request.

## 7. Downstream Prediction Payload

The consumer publishes the latest probability analysis to:

```text
worldcup.predictions.updated
```

Payload contains:

- match information when available.
- source prediction version.
- home win probability.
- draw probability.
- away win probability.
- fair decimal odds.
- confidence level.
- settlement status.

Fair odds formula:

```text
fair_decimal_odds = 1 / probability
```

## 8. Compatibility

The existing classes remain intact:

- `InMemoryEventBus`
- `JsonlEventBus`

No existing JSONL tests or local UI workflow require Kafka to be running.

## 9. Tests

Kafka tests do not require a live broker. They validate the critical engineering guarantees:

- `KafkaEventBus.publish_event` uses `match_id` as the Kafka key.
- `KafkaPredictionConsumerWorker` blocks duplicate `event_id`.
- Downstream prediction messages include `fair_decimal_odds`.

Run tests:

```powershell
python -B -m unittest discover -s tests
```

