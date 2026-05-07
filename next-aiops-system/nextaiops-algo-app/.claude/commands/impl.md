开始实现 todo 第 $ARGUMENTS 项。

执行步骤：
1. 仅动该 todo 涉及的文件，不准顺手改无关代码
2. 实现完成后跑相应检查并贴完整输出：
   - 涉及代码：`make test` + `make lint`
   - 仅文档/配置：`make lint`（适用时）
3. 测试失败时：分析根因 → 改实现
4. 完成后 commit，message 格式：
   `<type>(<scope>): <subject>`
   - type ∈ {feat, fix, refactor, test, docs, chore}
   - scope ∈ {core, algorithms, pipeline, viz, storage, cli, ui, smoke, ci, build}
5. commit 后停下，等我说「继续」再做下一项

禁止：
- 改测试断言以让测试通过
- try/except 吞异常或 pytest.skip
- 顺手优化无关代码
- 引入 PLAN 未声明的依赖
- 单次输出超过 200 行（多半在猜，停下报告）
