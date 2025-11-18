# 当前进度诊断（v0.5 基线）

> 依据 `PRD v0.5` 的目标，对代码库的现状进行横向比对，方便后续排期。

## 1. 数据与模型层

- 仅存在 `User`、`Group`/`Membership` 与 `Subscription` 三类 SQLModel，尚未覆盖别名、剧目、跨源映射、快照、呼啦圈最小镜像等模型；`init_db` 也只导入了 `User` 和 `Subscription`，意味着迁移脚本及其余表结构尚未落地。参见 `services/db/models/*.py` 以及 `services/db/init.py`。
- `services/db/connection.py` 仍直接返回 `sqlite3.connect`，未按照 PRD 约定配置 `SQLModel` 会话、WAL、`check_same_thread=False` 等参数，也没有统一的 `SessionLocal`/`engine` 管理。
- 仓库内不存在 `scripts/` 目录、`.env` 示例或任何 `import_v0_json.py`，因此历史 JSON -> SQLite 的迁移链路尚未启动。

## 2. 服务层与兼容层

- `services/` 目录只有 `crawler/`、`db/`、`system/` 三个子模块，没有 `user/`、`subscription/`、`group/`、`alias/`、`play/` 等服务实现，更没有 `compat/` 适配层。插件仍然通过 JSON DataManager 直接读写数据。参见 `plugins/Hulaquan/data_managers.py`。
- `plugins/Hulaquan/main.py` 内所有命令依旧依赖 `UsersManager`、`HulaquanDataManager` 等旧式 JSON 文件，尚未解耦 IO，也没有调用任何 service API。

## 3. 呼啦圈轮询 / 事件 / 快照链路

- 目前仍是插件内部的同步命令逻辑：`StatsDataManager`/`HulaquanDataManager` 手动管理 repo、关注、错误报告等结构，没有单独的轮询器、事件总线或快照表。也未见 `PlaySnapshot`、`HLQEvent`/`HLQTicket` 等模型或监听器。
- `services/crawler/` 虽然已经实现了 `AdvancedCrawlerClient`、连接池、熔断/健康探测，但这些能力尚未与呼啦圈数据流整合，未形成“轮询 → 变更写库 → 事件 → 快照”闭环。

## 4. 稳定性与可观测性

- 已实现 `services/system/network_health.py`、`error_protection.py`、`degradation.py` 等单体组件，但 NapCat 健康检查、自愈脚本、维护模式开关、分级日志目录 (`logs/framework.log` 等) 仍未出现。`main.py` 仍是最初的 NapCat 启动逻辑。
- 没有看到 `logs/` 目录、统一日志格式或告警脚本（如 `scripts/verify_logs.py`）。

## 5. 测试与验收

- `tests/` 目录只有 `tests/crawler/test_client.py`/`test_server.py` 等与爬虫相关的 benchmark/demo，尚无任何围绕 CRUD、别名解析、HLQ 流程或系统恢复的单测/压测脚本。
- 也没有 `pytest`/`tox` 配置或 CI 入口，尚无法验证 PRD 提到的 CRUD 覆盖率与轮询压测。

## 6. 汇总结论

| PRD 模块 | 当前状态 | 诊断 |
| --- | --- | --- |
| 数据模型 | 仅完成用户/群/订阅雏形 | 需要补齐 10+ 张表、迁移脚本、UTC 统一策略 |
| 服务层 & compat | 未落地 | 插件仍强耦合 JSON，需要服务 API 与适配器 | 
| 呼啦圈链路 | 未落地 | 只有旧 DataManager，缺少轮询/事件/快照 | 
| 稳定性/运维 | 部分工具 | 无 NapCat 自愈、维护模式、独立日志 | 
| 测试 | 仅有爬虫 demo | CRUD/集成/压测均未搭建 |

> 结论：截至当前提交，PRD v0.5 的核心重构尚处于“模型雏形 + 部分通用组件”阶段，尚未对旧插件/数据路径产生实质替换。建议优先完成：① 补齐 SQLModel + 迁移脚本；② 构建 service/compat 并让主插件只依赖 service；③ 实现 HLQ 轮询→事件→快照链路；④ 加入 NapCat 健康监控、自愈和日志分流；⑤ 补上 CRUD 单测与回归脚本。
