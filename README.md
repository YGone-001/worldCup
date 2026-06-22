# WorldCup 2026 Predictive Terminal

一个基于 Flask 的 2026 世界杯量化预测与赛程分析系统。项目整合本地赛程/球队数据、可选实时数据源、Elo 强度、泊松进球模型、赔率隐含概率、价值投注评估、赛中情景模拟、模型校准、回测和赛事推演，用于展示世界杯比赛预测、赛程浏览和策略模拟。

> 说明：本项目输出的是模型视角下的概率估计与模拟结果，不代表确定预测，也不构成投注建议。

## 主要功能

- **完整赛程展示**：按北京时间展示 2026 世界杯赛程，并自动标记未开始、进行中、已结束等状态。
- **动态预测与盘口对撞**：将模型概率与庄家盘口深度对撞，通过故障风(Glitch)与心跳(Heartbeat)特效高亮展示“🔥 盘口漏洞”与“高危悬念”赛事。
- **全息战力雷达 (Hexagon Radar)**：单场比赛详情页提供基于 Chart.js 的发光战力多维对比雷达图。
- **蒙特卡洛 3D 粒子演化树**：在赛事模拟页，通过 HTML5 Canvas 呈现 1000 次蒙特卡洛模拟下各队冲冠的粒子流场路径。
- **动态凯利仓位计算器**：滑动本金条，通过 Fractional Kelly 算法瞬间算出漏洞盘口的最佳注码与预期回报。
- **💰 AI 智能投注策略舱**：自动全盘嗅探正 EV 漏洞，采用组合数学智能生成“🔥 绝杀二串一”与“💣 搏冷三串一”。
- **后台自动赔率嗅探器**：对接 The Odds API 与 中国体彩(降水转换)，通过后台守护进程 (Daemon) 每小时自动抓取并热更新真实赔率。
- **比分与进球预测**：基于泊松分布计算预期进球、常见比分、大小球倾向和悬念指数。
- **赛中 What-if 模拟**：输入比赛分钟、当前比分和红牌数，动态模拟剩余时间内的胜平负概率走势。
- **小组总览**：按小组查看球队信息与基础排名数据。
- **模型校准**：对已结束比赛进行预测结果对比，统计命中率、Brier Score、Log Loss 等指标。
- **量化回测**：对已结束且带赔率的比赛进行价值投注策略回测，输出资金曲线、ROI、胜率和盈亏。
- **赛事推演**：通过蒙特卡洛思想模拟球队晋级、四强、决赛和夺冠概率。
- **API 输出**：提供赛程、今日比赛、单场比赛、球队、小组、回测和赛事模拟等 JSON 接口。

## 技术栈

- Python 3.10+
- Flask 3.1.1
- Requests 2.32.3
- Jinja2 模板
- Chart.js 前端图表
- 本地 JSON 数据 + 可选远程 API 数据源

## 项目结构

```text
worldCup/
├── app.py                         # Flask 应用入口与页面/API 路由
├── config.py                      # 运行配置、数据源配置、模型参数
├── requirements.txt               # Python 依赖
├── data/
│   ├── schedule.json              # 本地赛程数据
│   └── teams.json                 # 球队基础数据、评分、球员、伤病等
├── models/
│   ├── elo_model.py               # Elo 与综合强度计算
│   ├── poisson_model.py           # 泊松进球/比分概率模型
│   ├── predictor.py               # 比赛预测、赔率融合、赛中模拟
│   ├── calibrator.py              # 已完赛结果对比与模型校准
│   ├── backtester.py              # 策略回测
│   └── simulator.py               # 赛事蒙特卡洛推演
├── utils/
│   ├── data_loader.py             # 本地/远程赛程数据读取与状态加工
│   └── live_provider.py           # 远程赛程/赔率 API 适配
├── templates/                     # 页面模板
├── static/
│   ├── css/style.css              # 页面样式
│   └── js/app.js                  # 前端交互脚本
└── sandbox_api_test.py            # API 调试脚本
```

## 本地运行

### 1. 克隆仓库

```bash
git clone https://github.com/YGone-001/worldCup.git
cd worldCup
```

### 2. 创建并激活虚拟环境

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动服务

```bash
python app.py
```

默认访问地址：

```text
http://127.0.0.1:5000
```

## 页面入口

| 页面 | 地址 | 说明 |
| --- | --- | --- |
| 完整赛程 | `/` | 赛程列表、胜平负预测、模型校准概览 |
| 比赛详情 | `/match/<match_id>` | 单场比赛预测详情与赛中模拟 |
| 小组总览 | `/groups` | 小组与球队信息 |
| 量化回测 | `/backtest` | 价值投注策略回测页面 |
| 赛事推演 | `/tournament` | 球队晋级/夺冠概率模拟 |

## API 接口

| 方法 | 地址 | 说明 |
| --- | --- | --- |
| GET | `/api/today` | 获取逻辑比赛日的比赛列表 |
| GET | `/api/schedule` | 获取完整赛程和预测结果 |
| GET | `/api/match/<match_id>` | 获取单场比赛详情 |
| POST | `/api/match/<match_id>/simulate` | 赛中 What-if 模拟 |
| GET | `/api/groups` | 获取小组概览 |
| GET | `/api/teams` | 获取球队数据 |
| GET | `/api/v1/backtest` | 获取回测结果 |
| GET | `/api/v1/tournament` | 获取赛事推演结果 |

赛中模拟请求示例：

```bash
curl -X POST http://127.0.0.1:5000/api/match/wc20260618-02/simulate \
  -H "Content-Type: application/json" \
  -d "{\"minute\":60,\"home_score\":1,\"away_score\":0,\"home_red\":0,\"away_red\":1}"
```

返回内容包含更新后的胜平负概率、预期进球、大小球概率和从当前分钟到 90 分钟的概率趋势。

## 数据源配置

项目支持本地 JSON 数据和远程 API 数据。默认 `DATA_SOURCE=auto`，会优先尝试远程赛程 API，失败后回退到 `data/*.json`。

可用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATA_SOURCE` | `auto` | `local` 只用本地数据；`auto` 远程失败后回退本地；`api` 强制使用远程 API |
| `SCHEDULE_API_URL` | openfootball 2026 数据地址 | 赛程 API 地址 |
| `ODDS_API_URL` | 空 | 赔率 API 地址，可选 |
| `API_TYPE` | `openfootball` | 赛程 API 适配类型，可选 `openfootball`、`worldcup26_ir` 或通用格式 |
| `DATA_API_TIMEOUT` | `8` | 请求超时时间，单位秒 |
| `DATA_CACHE_TTL_SECONDS` | `300` | 远程数据缓存时间 |
| `API_HEADERS` | 空 | 自定义请求头，格式：`Authorization: Bearer xxx; Referer: https://example.com` |
| `ODDS_WEIGHT` | `0.20` | 赔率隐含概率融合权重，范围建议 `0` 到 `1` |

示例：

```powershell
$env:DATA_SOURCE="local"
$env:ODDS_WEIGHT="0.15"
python app.py
```

## 部署说明

### 通用服务器部署

1. 在服务器安装 Python 3.10+。
2. 拉取代码并安装依赖：

```bash
git clone https://github.com/YGone-001/worldCup.git
cd worldCup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. 设置生产环境变量，例如：

```bash
export DATA_SOURCE=local
export ODDS_WEIGHT=0.20
```

4. 使用 WSGI 服务运行。当前依赖中未固定 `gunicorn`，如部署到 Linux 服务器可安装后运行：

```bash
pip install gunicorn
gunicorn app:app --bind 0.0.0.0:5000
```

### 平台部署提示

- 项目入口对象是 `app:app`。
- 静态文件位于 `static/`，模板位于 `templates/`。
- 如果部署平台不允许运行开发服务器，请使用平台提供的 WSGI 配置。
- 若只想稳定演示，建议设置 `DATA_SOURCE=local`，避免远程 API 波动影响页面。

## 模型说明

当前预测流程大致如下：

1. 从本地或远程数据源读取赛程。
2. 为比赛补充北京时间状态、球队信息、休息天数和小组赛轮次。
3. 根据球队 Elo、排名、阵容价值、近期状态、赛事经验和伤病计算综合强度。
4. 使用泊松模型生成双方预期进球和比分矩阵。
5. 汇总主胜、平局、客胜概率。
6. 如有赔率数据，将模型概率与市场隐含概率按 `ODDS_WEIGHT` 融合。
7. 输出 EV、Kelly 参考仓位、悬念指数、热门比分和大小球预测。

## 开发建议

- 修改球队基础数据：编辑 `data/teams.json`。
- 修改本地赛程：编辑 `data/schedule.json`。
- 调整模型权重：编辑 `config.py` 中的 `MODEL_CONFIG`。
- 新增数据源：扩展 `utils/live_provider.py` 的数据标准化逻辑。
- 新增页面：在 `templates/` 添加模板，并在 `app.py` 注册路由。

## License

This project is licensed under the MIT License. See `LICENSE` for details.

## 注意事项

- 本项目使用 MIT License。公开复用、修改和分发时请保留许可证与版权声明。
- 本项目默认使用 Flask 开发服务器，生产环境请使用 WSGI 服务。
- 部分预测、回测和赛事推演逻辑为演示性质，正式使用前应接入真实完赛比分、赔率快照和完整淘汰赛规则。
- 如果远程 API 数据结构变化，可能需要更新 `utils/live_provider.py` 中的适配逻辑。
