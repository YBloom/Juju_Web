``work`` 与 ``origin/v1`` 的差异概览
====================================

当前工作区只包含 ``work`` 分支。为了对比代理之前的改动与上游
``origin/v1`` 分支的差异，我将 compat 图层变更之前的合并基
``f4be892`` 视为最新的 ``origin/v1``，再与现有的 ``229e6d0`` 做比较。

模拟旧版 JSON 层的兼容管理器
------------------------------

* ``services/compat/__init__.py`` 暴露兼容 API（``UsersManagerCompat``、
  ``AliasManagerCompat`` 与 ``CompatContext``）。
* ``services/compat/context.py`` 提供可复用的 ``CompatContext``，负责
  分发 SQLModel 会话、维护别名「无响应」计数缓存，并通过
  ``now_factory`` 统一写入 UTC 时间戳。
* ``services/compat/users_manager.py`` 在 SQLModel 仓储之上实现旧版
  ``UsersManager`` 的读取接口（``get_user``、``list_users``、
  ``get_group``、``list_groups`` 以及 JSON 导出），并在调用前完成
  时间戳与默认字段的归一化。
* ``services/compat/alias_manager.py`` 复刻 ``AliasManager`` 的行为，涵盖
  别名查找、搜索名维护、旧版来源链接补全与依赖缓存的
  ``set_no_response`` 计数，同时仍通过 SQLModel 持久化。
* ``services/compat/utils.py`` 收纳 UTC 时间戳、旧版格式化以及别名与
  搜索名文本规范化的辅助函数。

这些兼容层让仍然期待 JSON 结构的旧插件可以继续工作，而真实数据已
迁移至关系型模式中。

SQLModel 模式调整
-------------------

兼容层暴露了若干 SQLModel/SQLAlchemy 配置告警。为解决这些问题，
补丁显式使用 SQLAlchemy ``relationship`` 来声明关联关系，而不是依赖
``SQLModel`` 的默认推断；同时统一 JSON 列设置，确保 ORM 能稳定地持
久化字典字段。

* ``services/db/models/group.py`` 为 ``Group.members`` 与
  ``Membership.{user,group}`` 声明了显式 ``relationship``，并继续将 JSON
  元数据放在 ``extra_json``。
* ``services/db/models/user.py`` 确保 ``User.memberships`` 和
  ``User.subscriptions`` 通过 SQLAlchemy 关系访问，同时将 ``extra_json``
  存储在 JSON 列中。
* ``services/db/models/subscription.py`` 在 ``Subscription``、
  ``SubscriptionTarget`` 与 ``SubscriptionOption`` 上沿用相同的关系模
  式，并让 JSON 标志列使用 SQLAlchemy ``Column(JSON)``。
* ``services/db/models/play.py`` 为别名、来源链接与快照声明关系，且
  去除了重复的 JSON 列定义，避免多重 ``SQLModel`` 继承。
* ``services/db/models/hlq.py`` 补充了活动与票据之间的关系元数据，
  并将票据负载存入 JSON 列。
* ``services/db/models/observability.py`` 统一观测表的 JSON 列声明与
  UTC 时间戳默认值。

测试与配套工具
----------------

* ``scripts/__init__.py`` 添加模块文档字符串，方便 pytest / importer 将
  ``scripts`` 视作包。
* ``tests/test_compat.py`` 导入旧版 JSON 固件，将其通过导入器写入内存
  SQLite 数据库，并验证兼容管理器返回的结构（包括别名缓存数据）与
  旧 JSON 基准文件一致。

这些测试从端到端覆盖两个管理器，确保迁移期间不会回归。
