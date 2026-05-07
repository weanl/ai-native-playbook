启动 PR-$ARGUMENTS 的实现规划。

执行顺序：
1. 阅读 @CLAUDE.md 与 @AGENTS.md，简要复述红线条款 R1~R7（5 行以内）
2. 从 @docs/PLAN.md 提取 PR-$ARGUMENTS 的「范围」「关键设计点」「验收线」段落，原文引用
3. 列出本 PR 的 todo 清单，每项必须包含：
   - 文件路径（精确到 src/.../xxx.py）
   - 对应 AGENTS.md 的哪条红线（R1~R7 编号）
   - 验证方式（具体测试文件名或命令）
4. 标注本 PR 的验收线（逐条来自 PLAN.md，不得遗漏）

禁止：
- 写任何代码（本步只输出 plan）
- 引入 PLAN 未列出的依赖
- 改 core/ 既有抽象（如需改动必须先创建 ADR 草案）

我 review 通过后再用 `/impl <i>` 进入实现。
