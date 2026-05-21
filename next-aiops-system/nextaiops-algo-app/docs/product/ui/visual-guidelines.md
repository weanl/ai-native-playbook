# M2-024 视觉规范

## 设计目标

原型应像一个实验工作台，而不是模型生命周期管理后台。

视觉重点：

- 快速看懂数据来源和 schema 状态。
- 快速看懂实验配置和任务矩阵规模。
- 快速比较不同算法效果。
- 明确 failed / completed_with_failures 的状态。

## 信息密度

- 侧边栏展示品牌 + 功能入口 + 主流程摘要。
- 主区域按 workflow tab 线性推进，避免横向切换。
- 表格以扫描为主，避免大块解释文案。
- 指标卡展示关键数值：行数、异常点数、TP/FP、算法数、文件数、成功/失败单元数。

## 颜色体系

| 用途 | CSS 变量 | 色值 |
|---|---|---|
| 品牌与数据 | `--brand` | `#3157d5`（蓝色系） |
| 成功与完成 | `--success` | `#147a5c`（绿色系） |
| 复核与注意 | `--warning` | `#a55f12`（橙色系） |
| 阻断与失败 | `--danger` | `#b42318`（红色系） |
| 辅助信息 | `--muted` | `#667085`（灰色系） |

Badge 使用颜色变体：success / warning / danger / neutral / brand。

Notice 使用同色系变体：默认蓝 / success 绿 / warning 橙 / danger 红。

## 页面组件

### 侧边栏

- 品牌标识（品牌名 + 副标题）。
- 功能页面 radio-card。
- 主流程 notice。

### Workflow Tab

- 数据接入 / 数据预览 / 实验配置 / 任务管理 / 结果查看。
- 当前 tab 高亮（brand-soft 背景 + brand 色）。

### 指标卡

- 4 列 grid：metric-label + metric-value + metric-sub。
- 用于数据画像和实验结果摘要。

### Badge

- 圆角 pill：success / warning / danger / neutral / brand。
- 用于状态标记、schema 校验、实验类型。

### Notice

- 带边框信息块：默认蓝 / success 绿 / warning 橙 / danger 红。
- 用于操作提示、实验标识说明、路径说明。

### Drawer

- 右侧滑出详情面板。
- 用于子任务矩阵钻取。

### Fake Chart

- SVG 占位图：网格背景 + 曲线 + 异常段矩形。
- 用于指标曲线预览、结果曲线、overlay、heatmap 占位。

### Toast

- 右下角弹出消息：数据源切换、实验完成提示。

## 原型约束

- 单文件 HTML，不依赖 CDN、远程字体、外部 JS/CSS。
- 可直接浏览器打开。
- 桌面宽屏和常见笔记本视口可读。
- 不展示模型注册、manual promotion、回滚或生产发布页面。