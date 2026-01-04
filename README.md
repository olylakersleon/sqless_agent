# sqless_agent

数据分析 Agent 的指标映射与口径澄清系统。

## 目录
- `docs/PRD.md`：需求文档，覆盖背景、目标、核心流程、数据结构与里程碑。
- `sqless_agent/`：核心代码，包含 Metric Spec 模型、候选检索、不确定性门控、澄清流、专家路由与 SQL 生成（含专家协同卡片数据结构）。
- `sqless_agent/provenance.py`：基于历史 SQL 日志的意图-SQL 清洗、模板化、语义逆向与信任评分流水线。
- `demo.py`：使用内置示例资产跑通“查询 → 澄清 → SQL 生成”的最小示例。
- `app.py` + `static/`：轻量 HTTP 服务 + 原生前端实现的澄清界面，支持候选选择、三问澄清与 SQL 生成。

## 本地运行示例
```bash
python demo.py
```
输出将展示候选口径、澄清结果和生成的 SQL，方便验证端到端流程。

### SQL Provenance Mining（意图-SQL 知识库）

同一条 `demo.py` 也会运行“从历史 SQL 日志构建高质量意图-SQL 对”的离线流水线：

1. 物理层过滤：只保留成功且扫描量/耗时达到阈值的日志，并用 `authority_map` 控制白名单；自动对手机号/邮箱/身份证等 PII 做 `<MASKED>` 处理。
2. 结构化指纹：用 `SQLTemplateBuilder` 将 SQL 参数化（日期/数值 → `{param_n}`），提取表名并生成 Fingerprint。
3. 语义逆向：`SemanticIntentInferer` 基于表结构与表达式检测生成一句话业务意图摘要。
4. 信任评分：`TrustScorer` 按频次、执行者权重、近期性综合打分，淘汰噪音并沉淀高质量 Intent-SQL Pair；`IntentSQLStore` 支持按自然语言检索 Top-K 模版。

## 运行前后端体验

无需额外安装三方依赖，直接启动内置 HTTP 服务即可：
```bash
python app.py --host 0.0.0.0 --port 8000
```

浏览器访问 http://localhost:8000 ，输入业务需求即可体验候选检索、最小澄清与 SQL 生成的交互式界面。

前端界面支持：
- 2~5 张指标候选卡片（口径摘要、过滤、时间口径、示例 SQL）
- 最多三问的低摩擦澄清与可编辑槽位表单
- 冲突提醒（如结算口径日粒度）与确认页签字后再执行
- 专家协同卡片：推测 A/B、30 秒速批按钮、“都不对我来修正”槽位表单与转发外部专家
- 快速入口：左侧导航、顶部快捷标签与“GMV 趋势”等 Pills 会直接触发示例查询，自动加载候选/澄清/专家卡片，所有卡片与按钮均与后端 API 联动可点
