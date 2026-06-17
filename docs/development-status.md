# 开发搭建状态

## 已完成

- 创建 Python/FastAPI 服务骨架。
- 创建标准事件模型和标准预测输出模型。
- 创建内存版比赛状态存储。
- 创建基础实时预测引擎。
- 创建简化版锦标赛模拟服务。
- 创建 WebSocket 订阅入口。
- 创建 PostgreSQL、ClickHouse 初始化 SQL。
- 创建 Redis、Redpanda、PostgreSQL、ClickHouse 的 Docker Compose 蓝图。
- 创建基础单元测试。
- 新增本地 JSONL 事件总线，用于开发阶段模拟 Kafka 发布。
- 新增事件质量评分，覆盖重复事件、高延迟事件和缺失字段。
- 新增比赛状态查询接口。
- 新增运行状态查询接口。
- 新增最近事件审计接口。
- 新增单场预测历史接口。
- Web UI 升级为多视图控制台，支持实时预测、赛事模拟、数据质量、模型版本四类视图。
- Web UI 新增事件历史、质量审计历史和预测历史展示。
- 新增世界杯赛事进程 provider。
- 新增比赛选择器，支持按比赛切换分析上下文。
- 新增体彩口径胜平负概率分析接口，包含概率和公平十进制赔率。

## 当前实现边界

当前版本是开发用最小闭环，不是生产版。

- 事件存储暂时使用内存实现。
- 事件总线暂时使用 JSONL 文件实现。
- 预测模型是 baseline heuristic，不是真实训练模型。
- 模拟服务是占位实现，不是大规模 Ray Monte Carlo。
- Kafka、Redis、PostgreSQL、ClickHouse 配置已放好，但应用尚未接入真实适配器。
- 外部供应商连接器尚未实现。

## 下一阶段建议

优先级从高到低：

1. 将 WorldCupProgressProvider 替换为真实 FIFA/Sportradar/Opta provider。
2. 增加 Kafka event producer 和 consumer。
3. 增加 RedisPredictionStore 和 PostgresMetadataRepository。
4. 增加真实模型服务接口和模型版本元数据页。
5. 增加 feature worker，把状态更新从 API runtime 中拆出。
6. 增加性能压测和 WebSocket 连接测试。
