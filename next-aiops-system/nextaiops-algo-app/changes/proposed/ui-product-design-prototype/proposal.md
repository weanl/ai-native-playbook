# Proposal ID: M2-024

## 标题
持续学习工作台 UI 产品设计原型

## 动机
- **为什么做**：M1.6 已验证算法、批量实验与 Streamlit demo 的基础能力，但当前 UI 仍是围绕阶段功能逐步堆叠出来的页面结构。M2 当前更需要先把“不同数据集上的算法实验、批量比较、离线策略模拟和效果指标”讲清楚，再把胜出配置承接到模型生命周期主流程。M2-029 正式实现持续学习工作台前，需要先完成可评审的信息架构、用户旅程、页面蓝图、视觉规范、交互状态模型、流程图与本地静态 HTML 原型。
- **影响**：客户、评审者与实现者能在写 UI 代码或引入前端工程前，对平台如何进行数据实验、选择候选方向、模拟 auto-active 策略、解释效果指标，并最终承接“候选模型、上线决策、可追溯与回滚”形成一致认知。

## 范围
- **影响模块**：仅产品设计文档。
- **本 proposal 修改文件**：
  - `changes/proposed/ui-product-design-prototype/proposal.md`
  - `changes/proposed/ui-product-design-prototype/spec-diff.md`
  - `changes/proposed/ui-product-design-prototype/tasks.md`
- **proposal 通过后的 implementation 允许新增 / 修改文件**：
  - `docs/product/ui/user-journeys.md`
  - `docs/product/ui/page-spec.md`
  - `docs/product/ui/interaction-states.md`
  - `docs/product/ui/visual-guidelines.md`
  - `docs/product/ui/tech-decision.md`
  - `docs/product/ui/offline-model-lifecycle.drawio`
  - `docs/product/ui/prototype/index.html`
- **依赖**：无。implementation 不得新增运行时依赖或前端构建依赖。
- **语言约定**：本 proposal 及后续 M2-024 设计交付物默认使用中文；路径名、代码标识符、页面英文导航名、命令与必要技术名词可保留英文。

## 非目标
- 不直接重构 `src/nextaiops_algo/ui/app.py`。
- 不修改任何 `src/` 代码。
- 不修改 `tests/`。
- 不修改 `storage/schema.sql`。
- 不修改 `pyproject.toml`。
- 不修改 `core/` 既有接口。
- 不实现持续学习、模型训练、模型注册、模型晋级或回滚业务逻辑。
- 不新增前端工程。
- 不直接迁移到 React / Next.js。
- 不引入新运行时依赖或前端构建依赖。

## 设计
- **方案**：M2-024 是纯设计 change。implementation PR 只产出产品设计文档与基于 mock 数据的本地静态 HTML 原型。原型必须展示导航与代表性交互状态，但不得连接 pipeline、storage、Streamlit 或任何后端代码。
- **阶段重心**：M2 UI 叙事优先围绕实验平台闭环展开：`Data -> Experiments -> Batch Compare -> Candidate Direction -> Strategy Simulation -> Winning Config`。模型版本注册、manual promotion 与 active pointer 是最终承接主流程，不应压过当前阶段的数据实验和策略模拟重点。
- **M2 离线策略模拟**：设计中必须表达每日新增数据后的离线策略模拟。该能力是 dry-run / backtest / recommendation，不是无人值守真实 auto-active。页面必须展示策略决策和数据实验效果指标。
- **目标用户**：
  - 平台评估者：希望判断 NextAIOps 是否支撑持续学习与可控模型上线。
  - AIOps 运维人员：希望检查数据、运行实验、比较候选模型、执行晋级并追溯历史。
  - 算法工程师：希望解释候选模型为什么更好，以及它基于哪个数据版本学习。
- **客户演示主线**：
  1. 在 `Overview` 展示 active model 与平台健康状态。
  2. 在 `Data` 查看数据集版本、schema、fingerprint 与质量信号。
  3. 在 `Experiments` 运行或回看单算法实验。
  4. 在 `Batch Compare` 对比算法、参数与数据集组合，形成候选方向。
  5. 在 `Strategy Simulation` 模拟每日新增数据后的训练、评估与 auto-active 策略，输出效果指标和推荐结论。
  6. 在 `Continuous Learning` 解释胜出配置如何承接为训练输入、rolling window 与 train job。
  7. 在 `Models` 对比 candidate model 与 active model，并展示候选模型为什么可以上线的决策证据。
  8. 在 `History` 追溯晋级过程，并说明回滚依据。
- **信息架构**：
  - 主导航：`Overview`、`Data`、`Experiments`、`Batch Compare`、`Strategy Simulation`、`Continuous Learning`、`Models`、`History`、`Settings`。
  - 跨页面核心对象：dataset version、experiment run、batch run、strategy simulation run / report、train job、model version、promotion event、artifact。
- **模型晋级决策证据**：
  - 设计中必须定义 candidate model 的 evidence panel，用于回答“为什么这个模型可以上线”。
  - evidence panel 至少包含：训练数据版本、评估数据版本、回测窗口、candidate vs active 指标差异、退化项、数据质量摘要、漂移或分布变化提示、关键 artifact 链接、promote / rollback 审计记录。
  - 如果 evidence 不足，页面必须展示不可晋级或需人工复核的状态，而不是只展示 promote 按钮。
- **策略模拟效果指标**：
  - 单次实验效果：`precision`、`recall`、`f1`、`pa_f1`、误报数、漏报数。
  - 跨数据集稳定性：按 dataset version / rolling window 展示均值、最差值、方差或波动范围。
  - 策略模拟效果：`would_promote_count`、`blocked_count`、`needs_review_count`、模拟 active timeline、相对当前 active 的指标 delta、退化次数。
  - 数据可信度：`label_coverage`、evaluation mode、数据质量分、漂移提示、invalid / partial_failed 影响范围。
- **边界约束**：
  - M2 可以设计并后续实现离线策略模拟、效果指标报告和推荐结论。
  - M2 不做无人值守真实 auto-active，不自动修改真实 active pointer，不实现 scheduler、在线 serving 或生产流量切换。
- **领域生命周期状态**：
  - 数据版本状态：`draft`、`validated`、`invalid`、`archived`。
  - 训练任务状态：`queued`、`training`、`evaluating`、`completed`、`failed`、`cancelled`。
  - 模型版本状态：`candidate`、`rejected`、`promoted`、`active`、`superseded`、`archived`、`rolled_back`。
  - 晋级事件状态：`pending_review`、`approved`、`rejected`、`rolled_back`。
  - UI 通用状态与领域状态需要在 `interaction-states.md` 中区分说明，避免后续 M2-029 实现时把加载态、任务态和模型生命周期态混在一起。
- **原型要求**：
  - `docs/product/ui/prototype/index.html` 是可直接用浏览器本地打开的单个静态文件。
  - 只使用 mock 数据。
  - 支持所有主导航页面的基础切换。
  - 每个页面都包含“页面目标 / 用户动作 / 核心信息 / 下一步动作”。
  - 展示 `empty`、`loading`、`running`、`failed`、`partial_failed`、`candidate`、`active`、`archived` 等状态。
  - 原型必须自包含：mock 数据内联，不依赖 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
  - 原型至少需在桌面宽屏与常见笔记本视口下可读，关键表格、状态标签、按钮和页面说明不得明显遮挡或溢出。
- **技术选型评估要求**：
  - 评估继续使用 Streamlit、重构 Streamlit、迁移到 React / Next.js 或其他正式前端的边界。
  - 给出 M2-029 的后续建议：Streamlit 工作台实现、独立前端迁移 proposal，或阶段性混合方案。
  - `tech-decision.md` 必须给出可判定 rubric，至少覆盖：多页面信息架构、长任务状态刷新、Plotly / 大表格交互、状态管理、组件复用、离线 demo 成本、部署复杂度、未来认证 / 权限 / 审计扩展、M2 时间成本、M3 可演进性。
  - 评估结论必须说明推荐方案、接受的妥协、触发迁移到正式前端的条件，以及 M2-029 的建议边界。
- **备选方案**：
  - 直接重构 `src/nextaiops_algo/ui/app.py`：拒绝。M2-024 是 UI implementation 前置，不应被当前 Streamlit 页面结构反向锁定。
  - 立即创建 React / Next.js 工程：拒绝。M2 当前要求先完成设计与技术判断，不引入前端工程依赖。
  - 只写 Markdown、不做原型：拒绝。评审需要一个可本地打开、能直观看到核心页面与流程的具体产物。
- **取舍**：
  - 收益：降低 M2-029 返工风险，明确客户 demo 叙事，并保持 proposal 阶段不进入 UI 实现。
  - 成本：UI 代码改动需要等设计 review 完成后再启动。

## 验收标准
- [ ] 已文档化用户角色与核心用例。
- [ ] 已文档化客户演示主线：模型从哪些数据学习、学到了什么、为什么可以上线、如何追溯与回滚。
- [ ] 已文档化实验优先闭环：不同数据集、算法、参数、批量比较、策略模拟与候选方向选择。
- [ ] 已文档化全局导航与页面信息架构。
- [ ] 已定义 `Overview`、`Data`、`Experiments`、`Batch Compare`、`Strategy Simulation`、`Continuous Learning`、`Models`、`History`、`Settings` 的低保真页面结构。
- [ ] 已文档化 `Data -> Experiments -> Batch Compare -> Candidate Direction -> Strategy Simulation -> Winning Config` 优先实验流程。
- [ ] 已文档化 `Winning Config -> Continuous Learning -> Models -> History` 最终承接流程。
- [ ] 已定义 M2 离线策略模拟的效果指标与推荐结论展示方式。
- [ ] 已定义候选模型晋级 evidence panel，覆盖训练数据版本、评估数据版本、回测窗口、candidate vs active 指标差异、退化项、数据质量、漂移提示、artifact 与审计记录。
- [ ] 已定义 evidence 不足时的不可晋级或需人工复核状态。
- [ ] 视觉规范覆盖颜色、字体层级、表格、指标卡、状态标签、矩阵、详情区、空状态与错误状态。
- [ ] 交互状态覆盖 `empty`、`loading`、`running`、`failed`、`partial_failed`、`disabled`、`completed`、`candidate`、`active`、`archived`、`promoted`。
- [ ] 领域生命周期状态覆盖 dataset version、train job、model version 与 promotion event。
- [ ] UI 技术选型评估覆盖继续 Streamlit、重构 Streamlit 与正式前端迁移，并按 rubric 给出结论。
- [ ] implementation 产出 `docs/product/ui/user-journeys.md`。
- [ ] implementation 产出 `docs/product/ui/page-spec.md`。
- [ ] implementation 产出 `docs/product/ui/interaction-states.md`。
- [ ] implementation 产出 `docs/product/ui/visual-guidelines.md`。
- [ ] implementation 产出 `docs/product/ui/tech-decision.md`。
- [ ] implementation 产出 `docs/product/ui/offline-model-lifecycle.drawio`。
- [ ] implementation 产出 `docs/product/ui/prototype/index.html`。
- [ ] 原型可无需 dev server 或后端直接本地打开。
- [ ] 原型为自包含单文件，不依赖 CDN、远程字体、外部 JS、外部 CSS 或网络请求。
- [ ] 原型包含全部主导航页面并支持基础页面切换。
- [ ] 原型不调用 pipeline、storage、Streamlit 或外部服务。
- [ ] 原型在桌面宽屏与常见笔记本视口下无明显遮挡或溢出。
- [ ] implementation 不修改 `src/`、`tests/`、`storage/schema.sql`、`pyproject.toml`。
- [ ] M2-024 proposal 与后续设计交付物以中文为主。

## 时间线
- **预估工作量**：proposal review 通过后 1 到 2 天完成 implementation。
- **依赖关系**：M2-024 可独立于 M2-025 到 M2-028 推进，但阻塞 M2-029 UI implementation 决策。

## 相关信息
- ADR：不需要。本 proposal 不修改 `core/` 契约，也不绑定最终前端架构。
- 范围锚点：`docs/PLAN.md` 中的 `M2-024: ui-product-design-prototype`。
