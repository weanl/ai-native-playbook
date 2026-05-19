# M2-024 视觉规范

## 设计气质

NextAIOps 算法平台是面向 AIOps 运维、算法评审和模型生命周期治理的工作台。视觉方向应克制、清晰、可扫描，避免营销型 hero、夸张装饰和大面积单一色调。

关键词：

```text
专业
可追溯
状态清晰
证据优先
高信息密度
```

## 色彩

基础色：

- 页面背景：`#f6f8fb`
- 主内容背景：`#ffffff`
- 一级文字：`#172033`
- 二级文字：`#536176`
- 边框：`#d9e1ec`
- 弱背景：`#eef3f8`

强调色：

- 主操作：`#2563eb`
- 成功：`#16815f`
- 警告：`#b76b00`
- 错误：`#c2413d`
- 运行中：`#6d5dfc`
- 只读 / archived：`#6b7280`

使用约束：

- 不使用大面积紫色、深蓝或单一渐变作为主视觉。
- 状态色只用于状态标签、提示条、关键指标变化，不用于大片背景。
- 指标升降必须结合方向和语义，不能只用红绿；例如异常检测 F1 提升为正向，误报升高可能为负向。

## 字体层级

建议层级：

- 页面标题：24px / 32px，字重 700。
- 区块标题：18px / 26px，字重 700。
- 卡片标题：15px / 22px，字重 700。
- 正文：14px / 22px。
- 表格与状态说明：13px / 20px。
- 辅助信息：12px / 18px。

约束：

- 不用随 viewport 缩放的字体。
- 字间距保持默认。
- 按钮内文字不得换行后挤压图标；必要时缩短文案。

## 布局

全局结构：

- 左侧固定主导航。
- 顶部显示当前页面标题、上下文对象和关键动作。
- 主区域以全宽 section 和表格为主，避免卡片套卡片。
- 详情区可采用右侧 panel 或下方展开区。

宽度建议：

- 导航宽度：220px。
- 主内容最大宽度：无强制固定，优先利用桌面宽屏。
- 表格最小列宽明确，避免内容挤压。

响应原则：

- 桌面宽屏用于完整工作台体验。
- 常见笔记本视口必须无明显遮挡、溢出或按钮重叠。
- 原型不要求完整移动端体验，但内容不能在窄视口完全不可读。

## 导航

主导航项：

```text
Overview
Data
Experiments
Batch Compare
Continuous Learning
Models
History
Settings
```

导航规则：

- 当前页面高亮。
- 页面名称保持英文，便于与 proposal、后续实现和文件结构对应。
- 每个页面顶部用中文说明页面目标。

## 指标卡

指标卡用于展示需要快速扫描的高价值摘要：

- Active model。
- Candidate evidence completeness。
- Latest train job。
- Batch compare best candidate。
- Data quality score。

指标卡内容：

- 标题。
- 主值。
- 状态标签。
- 辅助说明。
- 可选趋势或 delta。

约束：

- 指标卡不承担复杂解释，复杂证据放到 evidence panel。
- 同一行指标卡高度一致。

## 表格

表格用于核心对象列表：

- Dataset versions。
- Experiment runs。
- Batch results。
- Train jobs。
- Model versions。
- History events。

表格要求：

- 第一列为对象 ID 或名称。
- 状态列靠前。
- 时间、版本、指标列可扫描。
- 行内动作最多 2 个，更多动作进入详情区。
- partial_failed 行必须有失败摘要入口。

## 状态标签

状态标签必须包含：

- 状态值。
- 语义颜色。
- 必要时配简短说明。

建议映射：

- `active` / `validated` / `completed`：绿色。
- `candidate` / `running` / `training` / `evaluating`：蓝紫色。
- `needs_review` / `partial_failed` / `pending_review`：橙色。
- `failed` / `invalid` / `blocked`：红色。
- `archived` / `superseded` / `cancelled`：灰色。

## Evidence Panel

Evidence panel 是 Models 页的核心设计，不是普通详情卡。

必须展示：

- 训练数据版本。
- 评估数据版本。
- 回测窗口。
- 指标差异。
- 退化项。
- 数据质量摘要。
- 漂移提示。
- artifact 链接。
- 晋级 / 回滚审计记录。

视觉规则：

- 用分组结构展示证据，不把所有内容堆进一张表。
- 对缺失证据使用明确 warning 或 blocked 状态。
- promote 动作必须贴近 evidence completeness，而不是页面右上角孤立按钮。

## 空状态

空状态必须说明：

- 当前为什么为空。
- 用户下一步可以做什么。
- 如果是筛选导致为空，需要提示清除筛选。

示例：

```text
暂无候选模型。完成一次 train job 后，这里会展示 candidate model 与晋级证据。
```

## 错误状态

错误状态必须包含：

- 错误摘要。
- 关联对象。
- 影响范围。
- 建议动作。

禁止只展示泛化文案，例如“出错了”。

## 矩阵与热力图

Batch Compare 页面可使用矩阵和热力图展示多算法对比。

要求：

- 颜色必须有图例。
- partial_failed 单元格不能被空白吞掉。
- 指标方向必须说明，例如 F1 越高越好。
- 点击或选中单元格时展示对应 run detail 摘要。

## 原型视觉约束

`prototype/index.html` 必须：

- 自包含 CSS 和 JS。
- 不依赖 CDN、远程字体、外部图片或网络请求。
- 在桌面宽屏和常见笔记本视口下可读。
- 不出现明显遮挡、按钮文字溢出、表格挤压到不可读。
