# 2026世界杯智能预测引擎当前实现功能说明

## 1. 文档目标

本文档说明当前工程已经实现的功能、接口、页面能力、数据流、测试覆盖和已知边界。

当前版本是一个可本地运行的最小业务闭环，目标是验证以下链路：

- 世界杯赛事进程获取。
- 选择指定比赛进行分析。
- 事件注入与比赛状态更新。
- 胜平负概率与体彩口径公平赔率展示。
- 数据质量审计。
- 预测历史与事件历史展示。
- Web UI 与后端 API 联动。

## 2. 当前运行入口

本地服务地址：

```text
http://localhost:8000/
```

启动命令：

```powershell
uvicorn apps.api.worldcup_api.main:app --reload --host 0.0.0.0 --port 8000
```

测试命令：

```powershell
python -B -m unittest discover -s tests
```

## 3. 已实现模块总览

| 模块 | 当前实现 | 说明 |
|---|---|---|
| Web UI 控制台 | 已实现 | 支持比赛选择、概率展示、事件注入、质量审计、预测历史 |
| 后端 API | 已实现 | 使用 FastAPI 提供 REST 和 WebSocket 接口 |
| 世界杯赛事进程 | 已实现种子 provider | 当前使用公开赛程种子数据，后续可替换为 FIFA/Sportradar/Opta |
| 比赛状态存储 | 已实现内存版 | 支持事件驱动更新比分、射门、xG、红黄牌 |
| 预测引擎 | 已实现 baseline heuristic | 当前为基础启发式模型，不是真实训练模型 |
| 体彩概率分析 | 已实现 | 输出胜平负概率和公平十进制赔率 |
| 数据质量服务 | 已实现 | 支持重复事件、高延迟、未来时间偏移、缺失字段等检查 |
| 事件总线 | 已实现 JSONL 开发版 | 用本地 JSONL 模拟 Kafka/Redpanda 发布 |
| Kafka/Redpanda 事件总线 | 已实现可选模式 | 使用 aiokafka，支持生产者、消费者、幂等拦截和下游预测发布 |
| 锦标赛模拟 | 已实现占位版 | 当前为简化模拟，后续替换为 Ray/Spark Monte Carlo |
| WebSocket 推送 | 已实现基础订阅 | 可按 match_id 订阅预测更新 |
| 基础设施蓝图 | 已实现 | Docker Compose 包含 PostgreSQL、Redis、Redpanda、ClickHouse |

## 4. Web UI 功能

页面入口：

```text
http://localhost:8000/
```

当前页面包含四个主视图。

### 4.1 实时预测

功能：

- 展示当前选中比赛。
- 展示比赛基础信息：阶段、小组、场次、开球时间、场馆、城市、状态。
- 展示胜平负概率。
- 展示公平十进制赔率。
- 展示比赛状态：比分、比赛时间、射门、xG。
- 展示简化球场态势图。
- 支持事件注入：
  - 主队射门
  - 客队射门
  - 主队进球
  - 客队红牌

### 4.2 赛事模拟

功能：

- 展示简化锦标赛模拟结果。
- 展示晋级概率、决赛概率、冠军概率。
- 当前模拟结果来自简化模拟器，不是完整赛制级 Monte Carlo。

### 4.3 数据质量

功能：

- 展示最近事件流。
- 展示事件是否被接受。
- 展示数据质量评分。
- 展示质量告警，例如：
  - duplicate_event
  - high_ingest_latency
  - event_time_future_skew
  - missing_team_id
  - missing_xg_estimate

### 4.4 模型版本

功能：

- 展示当前预测使用的模型贡献。
- 展示预测历史。
- 展示每次预测的版本号、置信度和概率轨迹。

## 5. 世界杯赛事进程

当前已实现 `WorldCupProgressProvider`。

文件：

```text
packages/engine/worldcup_engine/worldcup_progress.py
```

当前种子数据包含部分 2026 世界杯赛程：

| match_id | 比赛 | 状态 |
|---|---|---|
| wc2026_mex_rsa | Mexico vs South Africa | finished |
| wc2026_kor_cze | South Korea vs Czechia | finished |
| wc2026_can_bih | Canada vs Bosnia and Herzegovina | scheduled |
| wc2026_usa_par | United States vs Paraguay | scheduled |
| wc2026_qat_sui | Qatar vs Switzerland | scheduled |
| wc2026_bra_mar | Brazil vs Morocco | scheduled |
| wc2026_hai_sco | Haiti vs Scotland | scheduled |

说明：

- 当前 provider 是本地种子实现。
- 字段中保留 `source`，用于后续接入真实数据源。
- 后续可替换为 FIFA/Sportradar/Opta provider，不需要重写 UI。

## 6. 体彩概率分析

当前已实现胜平负概率分析接口。

接口：

```text
GET /api/v1/matches/{match_id}/lottery-analysis
```

输出内容：

- 比赛信息。
- 主胜概率。
- 平局概率。
- 客胜概率。
- 公平十进制赔率。
- 置信度。
- 是否已结算。
- 风险说明。

公平赔率计算方式：

```text
fair_decimal_odds = 1 / probability
```

说明：

- 当前展示的是“公平赔率”，没有加入返还率、机构水位、盘口调整和风控边际。
- 页面中明确标注：概率分析仅用于数据建模展示，不构成购彩建议。

## 7. 后端 API 清单

### 7.1 健康检查

```text
GET /health
```

返回服务状态。

### 7.2 运行状态

```text
GET /api/v1/runtime/status
```

返回：

- event_count
- prediction_count
- bus_message_count
- active_ws_connections

### 7.3 世界杯赛事进程

```text
GET /api/v1/worldcup/matches
```

返回当前 provider 中的比赛列表。

### 7.4 事件接入

```text
POST /api/v1/events
```

功能：

- 接收标准比赛事件。
- 做数据质量检查。
- 更新比赛状态。
- 生成新预测。
- 写入本地 JSONL 事件总线。

Kafka 模式下：

- API 只发布事件到 `worldcup.events.raw`。
- 后台消费者异步处理事件。
- 预测结果发布到 `worldcup.predictions.updated`。

### 7.5 最近事件

```text
GET /api/v1/events/recent?limit=20
```

返回最近事件审计记录。

### 7.6 单场最新预测

```text
GET /api/v1/matches/{match_id}/prediction
```

返回指定比赛最新预测。

### 7.7 单场预测历史

```text
GET /api/v1/matches/{match_id}/predictions/recent?limit=20
```

返回指定比赛最近预测历史。

### 7.8 单场比赛状态

```text
GET /api/v1/matches/{match_id}/state
```

返回指定比赛状态。

### 7.9 体彩概率分析

```text
GET /api/v1/matches/{match_id}/lottery-analysis
```

返回胜平负概率与公平赔率。

### 7.10 锦标赛模拟

```text
GET /api/v1/tournament/simulation/latest
```

返回简化锦标赛模拟结果。

### 7.11 WebSocket 预测订阅

```text
WS /api/v1/ws/predictions
```

订阅示例：

```json
{
  "action": "subscribe",
  "match_ids": ["wc2026_can_bih"]
}
```

## 8. 数据流说明

当前事件驱动链路如下：

```text
Web UI event button
  -> POST /api/v1/events
  -> DataQualityService
  -> InMemoryPredictionStore.apply_event
  -> BaselinePredictionEngine.predict
  -> InMemoryPredictionStore.save_prediction
  -> JsonlEventBus.publish_event / publish_prediction
  -> Web UI refresh
  -> GET lottery-analysis / state / recent events / prediction history
```

Kafka 模式数据流如下：

```text
Web UI event button
  -> POST /api/v1/events
  -> KafkaEventBus.publish_event
  -> topic: worldcup.events.raw
  -> key: match_id
  -> KafkaPredictionConsumerWorker
  -> duplicate event_id check
  -> state update
  -> prediction recompute
  -> topic: worldcup.predictions.updated
  -> WebSocket broadcast
```

## 9. 核心代码位置

| 功能 | 文件 |
|---|---|
| FastAPI 入口 | apps/api/worldcup_api/main.py |
| 运行时编排 | apps/api/worldcup_api/runtime.py |
| Web 页面 | apps/web/index.html |
| Web 交互逻辑 | apps/web/static/app.js |
| Web 样式 | apps/web/static/styles.css |
| 标准 schema | packages/domain/worldcup_domain/schemas.py |
| 预测引擎 | packages/engine/worldcup_engine/predictor.py |
| 预测聚合 | packages/engine/worldcup_engine/aggregator.py |
| 内存状态存储 | packages/engine/worldcup_engine/storage.py |
| 数据质量 | packages/engine/worldcup_engine/quality.py |
| 本地事件总线 | packages/engine/worldcup_engine/event_bus.py |
| Kafka 事件总线 | packages/engine/worldcup_engine/event_bus_kafka.py |
| Kafka 消费者 | packages/engine/worldcup_engine/consumer_worker.py |
| 世界杯进程 provider | packages/engine/worldcup_engine/worldcup_progress.py |
| 简化模拟器 | packages/engine/worldcup_engine/simulation.py |

## 10. 测试覆盖

当前测试目录：

```text
tests/
```

已覆盖：

- 进球事件推动主胜概率上升。
- runtime 事件接入、质量评分、事件总线写入。
- 重复事件不重复发布。
- Web UI 静态资源存在。
- Web UI 关键挂载点存在。
- 世界杯赛事 provider 能返回种子比赛。
- 已完赛比赛返回结算概率。
- 未开赛比赛返回开放概率。
- Kafka producer 使用 match_id 作为消息 key。
- Kafka consumer 使用 event_id 拦截重复消息。
- Kafka consumer 下游消息包含 fair_decimal_odds。

测试命令：

```powershell
python -B -m unittest discover -s tests
```

当前最近一次验证：

```text
Ran 10 tests
OK
```

## 11. 当前边界与限制

当前版本仍然是开发验证版，不是生产系统。

主要限制：

- 世界杯进程为本地种子 provider，不是实时官方 API。
- 预测模型为 baseline heuristic，不是真实训练模型。
- 体彩赔率为公平赔率，不包含返还率、水位、盘口、机构调整。
- 比赛状态存储为内存实现，服务重启后状态丢失。
- JSONL 事件总线仍是默认本地模式；Kafka/Redpanda 可通过环境变量启用。
- 锦标赛模拟为简化占位，不是完整赛制 Monte Carlo。
- WebSocket 只实现基础订阅，还未做断线恢复、鉴权、限流和横向扩展。
- 尚未接入 Redis、PostgreSQL、ClickHouse 的真实读写适配器。

## 12. 下一步建议

建议按以下优先级继续：

1. 接入真实赛事进程 provider：FIFA/Sportradar/Opta。
2. 在真实 Redpanda 环境中增加集成测试和 topic 初始化脚本。
3. 将内存状态替换为 Redis/PostgreSQL 持久化适配器。
4. 增加真实模型服务接口，拆分 baseline 与生产模型。
5. 增加体彩分析的返还率、盘口、冷热度和风险提示。
6. 增加比赛列表筛选：日期、状态、小组、球队。
7. 增加历史比赛回放，用于验证模型和 UI。
8. 增加权限、审计、限流和生产监控。

## 13. 结论

当前工程已经完成从架构文档到可运行产品原型的第一阶段落地。

系统已具备：

- 可选择比赛。
- 可查看赛事进程。
- 可注入事件。
- 可实时更新状态。
- 可输出胜平负概率和公平赔率。
- 可查看数据质量和预测历史。

该版本适合作为后续接入真实数据源、真实模型服务和生产级中间件的基础骨架。
