# M2-024 用户旅程

## 目标

本设计面向 M2 持续学习与模型生命周期管理工作台，目标是让客户能沿着一条清晰主线理解平台：

```text
模型从哪些数据学习 -> 学到了什么 -> 为什么候选模型可以晋级为 active -> 生效后如何追溯与回滚
```

本文只定义产品旅程与演示叙事，不定义后端 schema，不实现业务逻辑。

## 术语边界

M2-024 文档中如出现“上线 / 生效”，只表示模型版本在模型注册与生命周期管理中被标记为 `active` 或完成 `promoted` 事件。

这不代表 M2 要实现在线推理服务、生产流量切换、多租户权限或发布系统。相关能力仍属于 M2 范围外或后续 proposal。

## 用户角色

### 平台评估者

关注点：

- 平台是否能解释持续学习闭环，而不是只展示一次性实验结果。
- 数据、实验、训练、模型版本、晋级事件之间是否可追溯。
- 候选模型晋级为 `active` 前是否有足够证据支撑。

典型问题：

- 这个模型用的是哪一版数据？
- 新模型相比当前 active model 提升在哪里，退化在哪里？
- 如果生效后效果不好，能不能定位原因并回滚？

### AIOps 运维人员

关注点：

- 当前 active model 是否健康。
- 最近训练任务、批量实验、模型晋级是否成功。
- 失败或部分失败时应先看哪里。

典型问题：

- 当前系统正在训练什么？
- 哪个数据版本质量有问题？
- 候选模型是否可以晋级，还是需要人工复核？

### 算法工程师

关注点：

- 算法表现如何随数据版本变化。
- 候选模型的评估证据是否完整。
- artifact、指标、可视化和历史记录是否能支持复盘。

典型问题：

- 这次训练相对上次是否因为数据漂移导致变化？
- 哪些指标提升，哪些指标退化？
- 失败任务的输入、参数和 artifact 在哪里？

## 客户演示主线

### 1. Overview：先回答“现在系统怎么样”

演示目标：

- 展示当前 active model、最近训练任务、最近批量评估和系统健康状态。
- 告诉客户平台不是孤立页面，而是围绕模型生命周期组织。

关键叙事：

- 当前生效的是哪个模型版本。
- 最近一次训练是否完成，是否产生 candidate model。
- 是否存在需要处理的失败、部分失败或待复核事件。

下一步动作：

- 若有待复核 candidate model，进入 `Models`。
- 若数据质量异常，进入 `Data`。
- 若需要解释候选模型来源，进入 `Continuous Learning`。

### 2. Data：回答“模型从哪些数据学习”

演示目标：

- 展示 dataset version、schema、fingerprint、数据质量摘要。
- 解释训练、评估和回测窗口来自哪些数据版本。

关键叙事：

- 数据版本是持续学习闭环的起点。
- schema、fingerprint、质量摘要用于判断本次训练是否可信。
- invalid 或 archived 数据版本不能直接参与晋级证据链。

下一步动作：

- 从 validated 数据版本进入单算法实验或批量实验。
- 若数据质量不足，进入问题详情或回到数据准备流程。

### 3. Experiments：回答“单个算法学到了什么”

演示目标：

- 承接现有单算法实验能力，展示输入数据、算法参数、结果图、指标和诊断。
- 用较低认知成本解释一次实验结果。

关键叙事：

- 单算法实验用于快速理解某个算法在某个数据版本上的行为。
- 指标、异常点、阈值线、结果诊断共同解释模型输出。
- 单实验结果可以作为批量比较或候选训练的前置洞察。

下一步动作：

- 参数和算法确认后进入 `Batch Compare`。
- 若实验失败，查看错误状态和输入数据摘要。

### 4. Batch Compare：回答“哪个候选方向更可靠”

演示目标：

- 展示多个算法、参数或数据版本组合的排行榜、矩阵和热力图。
- 帮客户理解模型选择不是单点观察，而是可比较的评估过程。

关键叙事：

- 排行榜用于识别整体表现最好的候选。
- 矩阵和热力图用于识别稳定性、退化项和异常组合。
- partial_failed 不能被隐藏，需要保留失败原因和影响范围。

下一步动作：

- 选择表现稳定的候选配置进入 `Continuous Learning`。
- 对失败组合进入 run detail 或 history 追溯。

### 5. Continuous Learning：回答“平台如何持续学习”

演示目标：

- 展示 rolling window、训练数据集版本、train job、评估任务和候选模型产出。
- 解释持续学习不是自动变更 active model，而是先产生可评审 candidate。

关键叙事：

- 训练任务有明确输入、状态、参数和输出 artifact。
- queued、training、evaluating、completed、failed、cancelled 是任务状态，不等同于模型生命周期状态。
- completed train job 可能产生 candidate model，但 candidate 是否晋级需要证据评审。

下一步动作：

- completed job 进入 `Models` 查看候选模型证据。
- failed job 进入 `History` 查看失败上下文。

### 6. Models：回答“为什么这个模型可以晋级”

演示目标：

- 并排展示 candidate model 与 active model。
- 以 evidence panel 解释晋级判断。

证据面板必须覆盖：

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
- 关键 artifact 链接。
- promote / rollback 审计记录。

评估证据约束：

- `labeled` 模式且 label coverage 足够时，F1 / PA-F1 可作为晋级证据。
- `unlabeled` 模式下，F1 / PA-F1 不应作为晋级证据；页面只展示无标签诊断、漂移提示或人工复核入口。
- `proxy` 模式必须说明 proxy 来源和指标可信度，默认需要人工复核。

关键叙事：

- promote 按钮不是页面装饰，而是证据充足后的受控动作。
- evidence 不足时必须展示“需人工复核”或“不可晋级”。
- active、candidate、superseded、rolled_back 等状态构成模型生命周期。

下一步动作：

- evidence 充分：进入晋级确认。
- evidence 不足：进入相关数据、实验或训练任务详情。
- 已生效后：进入 `History` 查看审计记录。

### 7. History：回答“生效后如何追溯与回滚”

演示目标：

- 统一查询 dataset、experiment、batch、train job、model version、promotion event。
- 支持从事件回到证据链。

关键叙事：

- 每次晋级和回滚都应留下可审计记录。
- rolled_back 不是普通失败态，而是模型生命周期中的重要事件。
- 历史页用于复盘“当时为什么这么做”。

下一步动作：

- 从 promotion event 回到 model evidence。
- 从失败事件回到 train job 或 batch run。

## 核心闭环

```text
Data
  -> Experiments
  -> Batch Compare
  -> Continuous Learning
  -> Models
  -> History
```

闭环解释：

- `Data` 定义模型学习来源。
- `Experiments` 解释单次算法行为。
- `Batch Compare` 形成候选方向。
- `Continuous Learning` 将候选方向转化为训练任务与候选模型。
- `Models` 用 evidence 决定是否晋级。
- `History` 负责生效后的追溯与回滚。

## 异常旅程

### 数据质量不足

```text
Data invalid -> Experiments disabled -> Models evidence incomplete
```

页面需要明确说明不可继续的原因，而不是只隐藏操作。

### 批量实验部分失败

```text
Batch Compare partial_failed -> 展示成功结果 + 失败组合 + 影响范围
```

成功结果可继续评估，但失败组合必须保留上下文。

### 候选模型证据不足

```text
Models candidate -> evidence incomplete -> promote disabled -> 指向缺失证据来源
```

缺失项可能来自数据质量、评估窗口不足、指标退化或 artifact 缺失。

### 生效后回滚

```text
Active model abnormal -> History promotion event -> Models previous version -> rollback audit
```

回滚必须展示来源事件、目标版本和原因。
