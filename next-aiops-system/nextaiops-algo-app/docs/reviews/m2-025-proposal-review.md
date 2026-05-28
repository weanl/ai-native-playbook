# M2-025 Proposal Review（rolling-experiment-data-layer）

## 结论
- **结论**：建议 **有条件通过（需先修正 2 个高优先级点）**。
- **原因**：整体分层与目标清晰，且明确保持 `core/` 不变；但当前文档在“日期规范化”和“切分边界约束”上有实现歧义，后续很容易在 M2-026 引擎接入时出现不可复现或样本泄漏问题。

## 高优先级问题（建议阻塞合入）

### 1) 日期分区的规范化规则未定义（会导致跨环境分区不一致）
- 当前 proposal 仅写“按日期列切分”，但未定义：
  - 时区处理（UTC / 本地时区 / naive timestamp）
  - timestamp 到 `YYYY-MM-DD` 的截断规则（先转时区再取 date，还是直接字符串截断）
  - 数值时间戳（秒/毫秒）识别策略
- 风险：同一份输入数据在不同时区/运行环境可能切出不同 `DayPartition`，破坏 R3 复现性。
- 建议补充到 `proposal.md` 与 `spec-diff.md`：
  - 统一约定：先解析为 UTC，再按 UTC date 分区；
  - 对数值 timestamp 明确按秒或毫秒推断规则（例如 `>=1e12` 视为毫秒）；
  - 解析失败行的处理策略（报错或剔除并计数）。

### 2) `split_train_validate` 的时间边界语义不够明确（可能引入泄漏）
- 当前描述为“复用 `split_by_time` 逻辑”，但没有明确：
  - 是“按行比例切分”还是“按时间点切分”；
  - 当存在同一 timestamp 的多行数据时，是否允许落在 train/validate 两侧；
  - ratio 极值（0/1）和最小样本量约束。
- 风险：验证集可能混入训练时间点的同时刻样本，造成评估偏乐观。
- 建议：在 AC 中增加边界验收项：
  - 验证集最早时间必须严格晚于（或不早于，需定一条）训练集最晚时间；
  - ratio 不在 `(0,1)` 时抛 `ValueError`；
  - 样本过少时的行为（报错或最小切分策略）写清楚。

## 中优先级建议（非阻塞）

1. **`partition_tables` 入参冗余**：既传 `table` 又传 `partitions`，建议明确冲突处理（以 `partitions` 为准还是重新计算）。
2. **`DayPartition.date` 类型**：建议用 `datetime.date`（序列化为字符串）而不是裸 `str`，减少非法值。
3. **`exclusion_reason` 枚举化**：建议定义受控枚举（如 `NO_LABEL_COLUMN` / `LOW_LABEL_COVERAGE` / `TIMESTAMP_PARSE_ERROR`），便于后续 UI 与统计分析。
4. **验收项可测性**：`make smoke` 对本提案的直接关联较弱，可改为“不得引入 smoke 回归”并强调新增单测/集成测覆盖表格。

## 正向评价
- 分层意识正确：将 `DayPartition` 放在 `pipeline/`，避免污染 `core/`。
- 变更范围克制：新增文件，不改既有接口，回滚成本低。
- 任务拆分清晰：实现与测试任务一一对应，便于并行推进。

## 建议的最小修订清单
1. 在 `proposal.md` 增加“时间规范化策略”小节（时区、秒/毫秒、解析失败）。
2. 在 `proposal.md` 的 `split_train_validate` 增加输入合法性与边界语义。
3. 在 `Acceptance Criteria` 增加 3 条可执行断言：
   - 时区与日期截断一致性；
   - train/validate 时间边界；
   - ratio 非法值处理。
4. 在 `tasks.md` 增补对应单元测试项（timestamp 规范化、ratio 边界、同时刻样本）。


## 对“验收方式是否明确、有效”的专项评估

### 当前判断
- **明确性：部分明确，但不充分**。已有 `Acceptance Criteria` 与 `Verification Steps`，但仍缺少若干“可判定边界”的精确定义（尤其是时区归一、时间切分边界、非法参数处理）。
- **有效性：中等**。可以覆盖主路径“分区 → 窗口 → 切分”，但对高风险失败模式（数据泄漏、跨时区不一致、极小样本）覆盖不足。

### 主要缺口（影响验收有效性）
1. **通过标准偏流程化，缺少结果断言**：`make test/lint/smoke` 是过程检查，不等于功能验收。
2. **关键边界无可执行断言**：`ratio` 边界、同 timestamp 跨集合、cutoff 无有效分区等场景缺“输入-输出”级断言。
3. **与提案目标耦合度不足**：`make smoke` 与本提案直接关系较弱，无法有效证明滚动数据层能力正确。

### 建议的“有效验收”最小基线
- **功能断言（必须）**
  - 分区数量、日期顺序、`status` 与 `exclusion_reason` 精确匹配预期。
  - `cumulative_training_window` 在给定 `cutoff_day` 下行数与时间范围精确匹配。
  - `split_train_validate` 的 train/validate 时间边界满足约束，且 `ratio` 非法值触发 `ValueError`。
- **鲁棒性断言（建议）**
  - 数值 timestamp（秒/毫秒）与字符串 timestamp 在 UTC 归一后分区结果一致。
  - 全部分区 excluded、或 cutoff 前无 valid 分区时，错误类型与报错信息可判定。
- **回归断言（必须）**
  - 新增单测、集成测试通过，且不引入现有 pipeline 行为回归（`run_experiment/run_batch` 相关测试保持通过）。

> 结论：目前 proposal 的验收方式“有框架但不够可判定”。补齐上述断言后，验收将更明确且有效。


## 补充评审：仅有编号、无原生时间戳的数据集如何适配滚动策略

### 背景与问题
很多时序异常检测数据集只有递增编号（index/step/id），没有可解析的真实时间戳。若严格要求 `TIMESTAMP` 才能进入日分区，会导致这类数据在 M2 滚动实验中“全量不可用”。

### 建议结论
- **不建议一刀切失败**。
- 建议在 M2-025 增加“**逻辑时间（synthetic timestamp）适配模式**”：允许用户提供 `start_time + interval`，将编号列映射为可分区时间轴，再复用同一套滚动分区/窗口逻辑。

### 建议方案（兼容现有设计）
1. **新增可选配置（仅 pipeline 层）**
   - `time_index_column: str | None`：编号列名（如 `step`/`id`）。
   - `synthetic_start_time: str | None`：起始时间（ISO-8601，如 `2026-01-01T00:00:00Z`）。
   - `synthetic_interval: str | None`：步长（如 `1min`/`5s`/`1h`）。
2. **启用条件（建议）**
   - 当输入无 `TIMESTAMP` 角色，且上述 3 项配置齐全时，自动生成临时 timestamp 列（仅在 rolling_data 内部使用或以明确列名输出）。
   - 当输入既无 `TIMESTAMP`，配置也不完整时，才抛 `SchemaValidationError`。
3. **生成规则（保证复现）**
   - 第 `i` 行时间 = `start_time + i * interval`（或按 `time_index_column` 数值偏移）；
   - 统一转 UTC 后再做 `YYYY-MM-DD` 日分区；
   - `interval` 必须为正，`start_time` 必须可解析，否则 fail-fast。

### 验收层面的新增要求（建议写入 AC）
- 给定仅编号数据 + `start_time/interval`，可成功构建日分区与累积窗口。
- synthetic 模式下，同一输入重复运行分区结果一致（复现性）。
- 配置缺失或非法（负 interval、不可解析 start_time、非单调编号）时，报错信息可判定。
- 当真实 `TIMESTAMP` 存在时，默认优先真实时间戳（避免误覆盖）。

### 风险与边界
- synthetic 时间仅用于“滚动切分与评估流程驱动”，不等价于真实业务事件时间；评审/报表中应标注来源（real/synthetic）。
- 若编号存在缺口或重排，必须先定义排序与去重策略，否则窗口边界会漂移。

> 结论：针对“只有编号无时间戳”的数据，应提供可配置的 synthetic timestamp 适配，而不是统一失败。这样既保持 R3 复现性，也提升滚动策略可用性。


## 最终评审意见（提炼版）

### 最终结论
- **结论：有条件通过（Conditionally Approve）**。
- **通过前置条件（必须全部满足）**：
  1. 明确并固化“时间规范化”规则（UTC 归一、秒/毫秒识别、解析失败处理）。
  2. 明确 `split_train_validate` 的边界语义与非法参数处理（避免泄漏，可判定失败）。
  3. 补齐与上述规则一一对应的可执行验收断言（单测 + 集成测试）。

### 是否明确、有效
- **当前验收方式：部分明确，但仍不充分**。
- **有效验收标准**应从“跑命令”升级为“可判定结果断言”：
  - 分区结果正确（数量/顺序/状态/排除原因）；
  - 窗口结果正确（cutoff 前累积范围与行数）；
  - 切分边界正确（时间不穿越 + ratio 非法值 fail-fast）；
  - 异常路径可判定（配置缺失、解析失败、无有效分区）。

### 对无时间戳数据集的最终建议
- **不应直接失败**。
- 建议支持 `synthetic timestamp` 适配：当无原生 `TIMESTAMP` 时，可通过 `time_index_column + synthetic_start_time + synthetic_interval` 生成逻辑时间，纳入同一滚动分区策略。
- 该模式需满足：可复现（同输入同输出）、可追溯（标注 real/synthetic）、有边界（非法配置 fail-fast）。

### 建议落地顺序
1. 先修订 proposal/spec-diff/tasks，补齐语义与 AC；
2. 再实现 `rolling_data.py` 与测试；
3. 最后以测试报告验收是否达到“可判定、可复现、无泄漏”。

> **最终意见**：该 proposal 方向正确、分层合理，具备推进价值；在完成上述 3 项前置修订后即可进入实现阶段。
