# Claude Code 入口约定

> 每次进入本仓库的 AI 会话，请先阅读本文件，并在首次回复前**简要复述红线条款**。

## 项目当前阶段
- 代号：**NextAIOpsAlgoApp / M0**（Walking Skeleton）
- 项目定位：见 @README.md
- 系统总览：见 @docs/NextAIOpsSystem.md
- 范围：见 @docs/architecture/M0-skeleton.md
- 完整规约：见 @AGENTS.md（必读）
- 任务拆解：见 @docs/PLAN.md

## 红线（违反即停）
1. **稳定/可变分离**：`src/nextaiops_algo/core/` 内的接口未经 ADR 不得修改
2. **算法接入契约**：算法必须实现 `core/algorithm.py::Algorithm` + 任务子协议（如 `AnomalyDetector`），注册到 REGISTRY；I/O 统一为 `Table`
3. **复现性**：每次 run 必须落库 run_id / params / metrics / artifacts 路径，且相同输入产生一致结果
4. **冒烟必过**：新算法必须使 `make smoke ALG=<name>` 通过；任何 PR 必须 `make test` 全绿
5. **不改测试过测试**：测试失败必须改实现；禁止改断言、禁止 try/except 吞异常、禁止 skip
6. **不越界**：每个 PR 仅修改 PLAN.md 当前 PR 列出的范围；引入新依赖必须先在 PLAN 声明
7. **范围外不做**：在线推理、多租户、流式接入、AutoML、MLflow、前端工程化

## 工作范式
- 收到任务 → 列 plan（不写代码）→ 等人 review → 逐项实现 → 跑测试 → 自检 → 提交
- 不确定先问，不猜领域语义；卡壳 30 分钟必停下报告
- 触碰红线立即停下，不自行恢复

## 常用命令
`make dev` `make test` `make lint` `make smoke ALG=<name>` `make demo`

## Slash Commands
`/new-pr <N>` 启动 PR 规划 ｜ `/impl <i>` 实现 todo 第 i 项 ｜ `/self-check` 收尾自检 ｜ `/correct <偏离点>` 纠偏
