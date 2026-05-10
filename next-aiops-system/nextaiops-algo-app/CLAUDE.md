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

## 血泪教训（PR-1~PR-5 实战总结）

> 违反即停，不要自行补救。

| 教训 | PR 实例 | 预防措施 |
|------|--------|----------|
| 分支必须先创建 | PR-5 在 main commit 后补救 | `/new-pr` 后立即 `git checkout -b feat/pr-N-slug` |
| commit 在 main 而非分支 | PR-5 直接在 main 提交 | 实现前检查 `git branch -vv`，确认在 feat/pr-* 分支 |
| amend 后普通 push 失败 | PR-4 SHA 变化被拒绝 | 用 `git push --force-with-lease origin <branch>` |
| DataFrame index 不重置 | PR-4 + PR-5 连续踩坑 | 用业务列（timestamp）对齐，而非 DataFrame.index |
| 跨 PR bug 越界 | PR-4 修 PR-3 bug、PR-5 修 PR-4 bug | PR 描述明确说明越界理由，最小改动 |
| CI lint 高频失败 | PR-1~PR-5 共 10+ 次 | commit 前跑：`pytest` + `ruff check` + `mypy --strict` |
| 测试不改全局状态 | PR-2 清空 REGISTRY | 用唯一命名，不清空全局注册表 |

### 分支管理正确流程

```bash
# 1. 同步 main
git checkout main && git pull

# 2. 创建分支（规划后立即执行）
git checkout -b feat/pr-N-<slug>

# 3. 实现循环：实现 → pytest → ruff → mypy → git add → git commit

# 4. 推送分支
git push -u origin feat/pr-N-<slug>

# 5. 创建 PR，等待 CI + merge
```

跨 PR Bug 处理

发现 → 立即修复 → PR 描述说明越界 → 最小改动

越界说明模板：
## ⚠️ 越界说明
文件 `<path>` 修改超出 PR-N 范围，**理由**：
- PR-M 遗留 bug：<描述问题>
- 发现时机：<集成测试 / 冒烟测试>
- 属于必要修复，否则本 PR 无法通过

测试金字塔

冒烟测试 (效果验证) ← 发现 PR-4 bug (F1=0)
  ↑
集成测试 (流程验证) ← 发现 PR-3 bug (index 对齐)
  ↑
单元测试 (边界验证)
