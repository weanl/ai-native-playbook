# M2-024 交互状态模型

## 设计原则

状态必须分层表达，避免把 UI 加载态、长任务状态、数据生命周期和模型生命周期混在同一个标签里。

```text
UI 通用状态：页面或组件当前如何呈现
长任务状态：训练、实验、批量任务正在什么阶段
领域生命周期状态：数据、模型、晋级事件在业务链路中的位置
动作可用性状态：用户当前是否可以执行某个动作，以及为什么
```

## UI 通用状态

| 状态 | 含义 | 页面表现 | 用户动作 |
|---|---|---|---|
| `empty` | 没有可展示对象 | 空状态说明 + 下一步入口 | 创建、导入或切换筛选 |
| `loading` | 页面或组件加载中 | 骨架屏或轻量 loading | 暂不可操作 |
| `running` | 有后台任务进行中 | 进度条、状态标签、刷新提示 | 可查看详情，关键动作 disabled |
| `failed` | 当前对象失败 | 错误摘要 + 上下文 + 跳转入口 | 查看详情、重试或回溯 |
| `partial_failed` | 批量对象部分失败 | 成功结果与失败组合并列展示 | 使用成功结果，同时追踪失败项 |
| `disabled` | 操作不可用 | 禁用按钮 + 原因说明 | 补齐前置条件 |
| `completed` | 任务完成 | 成功状态 + 产物入口 | 查看结果或进入下一步 |

## 数据版本状态

| 状态 | 含义 | 允许动作 | 禁止动作 |
|---|---|---|---|
| `draft` | 数据已导入但未验证 | 查看概要、触发验证 | 作为晋级证据 |
| `validated` | 数据通过基础校验 | 实验、批量评估、训练、作为 evidence | 无 |
| `invalid` | 数据质量不足或 schema 不合法 | 查看错误、重新导入 | 实验、训练、晋级证据 |
| `archived` | 历史数据，仅用于追溯 | 查看、追溯历史 | 新训练、晋级证据 |

展示要求：

- Data 页面必须展示状态、时间范围、schema 摘要、质量摘要。
- invalid 状态必须说明至少一个原因。
- archived 状态不能与 failed 混用；archived 是生命周期状态，不代表错误。

## 训练任务状态

| 状态 | 含义 | 页面表现 | 下一步 |
|---|---|---|---|
| `queued` | 等待执行 | 队列位置或等待说明 | 等待或取消 |
| `training` | 正在训练 | 训练进度、输入数据、参数摘要 | 查看 job detail |
| `evaluating` | 正在评估 | 评估窗口、当前指标占位 | 等待结果 |
| `completed` | 训练与评估完成 | 输出 artifact、candidate model 链接 | 进入 Models |
| `failed` | 训练或评估失败 | 错误摘要、输入上下文、artifact 状态 | 查看 History 或重试 |
| `cancelled` | 被取消 | 取消原因、操作者、时间 | 追溯或重新排队 |

展示要求：

- `training` 和 `evaluating` 是任务阶段，不能直接表示模型可晋级或生效。
- `completed` 只代表 train job 完成，不代表 candidate model 可晋级。
- `failed` 必须保留输入数据版本、算法配置和错误摘要。

## 模型版本状态

| 状态 | 含义 | 页面表现 | 用户动作 |
|---|---|---|---|
| `candidate` | 候选模型，等待证据评审 | 候选标签 + evidence panel | 查看证据、请求晋级 |
| `rejected` | 候选模型被拒绝 | 拒绝原因 + 关联证据 | 复盘 |
| `promoted` | 已通过晋级动作 | 晋级事件链接 | 查看审计 |
| `active` | 当前生效或演示主模型 | active 标签 + 当前指标 | 监控、对比、回滚 |
| `superseded` | 曾经 active，已被新模型替代 | 历史标签 | 回滚候选 |
| `archived` | 保留用于审计，不再参与操作 | 只读标签 | 查看历史 |
| `rolled_back` | 因回滚事件被撤下或作为回滚来源 | 回滚事件链接 | 复盘 |

展示要求：

- `active` 只能有一个主版本，原型中也应遵守。
- `candidate` 必须配 evidence panel。
- `promoted` 是动作结果，`active` 是当前生效状态，两者不要混用。
- `rolled_back` 必须链接到 rollback event。

## 晋级事件状态

| 状态 | 含义 | 页面表现 |
|---|---|---|
| `pending_review` | 晋级待复核 | 待审批标签 + 缺失或待确认项 |
| `approved` | 晋级被批准 | 审批记录 + active 变化 |
| `rejected` | 晋级被拒绝 | 拒绝原因 + 证据链接 |
| `rolled_back` | 发生回滚 | 前后模型版本 + 回滚原因 |

展示要求：

- 晋级事件必须展示原因、目标模型、来源模型、时间和证据摘要。
- 静态原型只展示状态，不实现真实审批动作。

## Evidence 完整度状态

| 状态 | 含义 | Promote 表现 |
|---|---|---|
| `sufficient` | 关键证据齐全，无阻断退化 | 可展示晋级入口 |
| `needs_review` | 有退化或漂移提示，需要人工判断 | 晋级入口需复核提示 |
| `incomplete` | 关键证据缺失 | 晋级入口 disabled |
| `blocked` | 数据 invalid 或 artifact 缺失 | 禁止晋级，展示阻断原因 |

Evidence panel 必须至少展示：

- 训练数据版本。
- 评估数据版本。
- 回测窗口。
- 标签覆盖率。
- 评估模式：`labeled` / `unlabeled` / `proxy`。
- 指标可信度。
- candidate vs active 指标差异。
- 退化项。
- 数据质量摘要。
- 漂移或分布变化提示。
- 模型 artifact ID / path / checksum / version。
- 算法名称、参数、seed。
- train job ID 与 experiment run ID。
- artifact 链接。
- promote / rollback 审计记录。

评估指标规则：

- `labeled` 模式可将 F1 / PA-F1 作为晋级证据，但必须展示 label coverage。
- `unlabeled` 模式不得把 F1 / PA-F1 作为晋级证据，只能展示无标签诊断、漂移提示或人工复核入口。
- `proxy` 模式必须说明 proxy 来源和可信度，默认进入 `needs_review`。
- 指标可信度不足时，Promote 表现不得是直接可晋级。

## 策略模拟效果指标

M2 若实现离线 `auto-active` 策略模拟，页面必须同时展示策略决策与数据实验效果指标。

模型实验指标：

- `precision`、`recall`、`f1`、`pa_f1`。
- 误报数、漏报数。
- candidate vs active 指标 delta。

跨数据集稳定性指标：

- 按 dataset version / rolling window 展示指标均值、最差值和波动范围。
- 标记 partial_failed 组合及其影响范围。

策略模拟指标：

- `would_promote_count`、`needs_review_count`、`blocked_count`。
- 模拟 active timeline。
- 自动切换次数、退化次数、回滚建议次数。

数据可信度指标：

- `label_coverage`。
- evaluation mode：`labeled` / `unlabeled` / `proxy`。
- 数据质量分、漂移提示和 invalid 分区影响。

## 交互规则

- 禁用按钮必须说明原因，不能只置灰。
- 失败状态必须提供可定位上下文，例如 dataset version、run id、job id 或 model version。
- partial_failed 状态必须同时保留成功结果和失败列表。
- 页面切换不应丢失当前选中的核心对象；静态原型可用 mock 状态模拟这一点。
- 所有状态标签应使用统一命名，避免中文文案和英文状态值脱节。
