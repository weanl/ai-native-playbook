# M2-024 MVP 技术取舍

## 当前结论

M2-024 继续使用自包含静态 HTML 原型表达产品设计，不引入前端工程或运行时依赖。

原因：

- 当前仍在确认滚动实验与 auto-active 策略语义。
- 原型目标是评审用户旅程，不是落地实现。
- 单文件 HTML 足够演示导入数据、策略配置、日循环和算法排行。

## M2-029 建议

若进入实现，可优先在现有 Streamlit 工作台内实现 MVP：

```text
Data Import
Policy Config
Rolling Experiment Runner
Results / Ranking
```

不建议在此时迁移 React / Next.js。

## 实现边界

MVP 实现需要支持：

- 多天数据导入与 day partition。
- 训练周期配置，默认 1 天。
- auto-active 策略配置，默认最新训练模型 active。
- 按 cutoff day 滚动训练与验证。
- 按 active interval 推理。
- prediction ledger。
- 算法效果排行。

MVP 不实现：

- 真实模型注册表。
- manual promotion。
- 生产 active pointer 修改。
- online serving。
- 流量切换。
- 多租户权限。

## 迁移触发条件

后续出现以下需求时，再考虑正式前端：

- 需要复杂多角色审批。
- 需要大型交互式图表和批量实验矩阵编辑。
- 需要长任务实时协作和多人审计。
- 需要权限、租户、发布链路等产品级治理能力。
