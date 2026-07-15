# DevSquad 设计准则 (DESIGN.md)

> **文档类型**: 项目设计准则 (Design Guidelines)
> **来源理念**: impeccable PRODUCT.md + DESIGN.md context protocol
> **用途**: UIUXAnalyzer 审计时加载本文件，按项目特定设计准则检测
> **最后更新**: 2026-07-15 (V4.1.0)
> **关联**: [GLOSSARY.md](GLOSSARY.md) | [SPEC.md](SPEC.md) | [ADR-001](../adr/ADR-001-four-doc-system.md)

---

## 一、视觉风格

### 1.1 色系

- **主色系**: Morandi（低饱和度，非刺眼）
  - 符合用户偏好：舒适配色，避免刺眼 emoji 和高饱和度色彩
  - 参考：莫兰迪色系（灰粉、灰蓝、灰绿、灰紫等低饱和度色调）
- **禁止**:
  - 紫蓝渐变（purple-to-blue gradient）— AI 前端反模式
  - 高饱和度原色（#FF0000 纯红等）用于大面积背景
  - 灰字彩底（gray text on colored background）— 可读性差

### 1.2 色彩空间

- **推荐**: OKLCH 色彩空间（感知均匀，比 sRGB 更符合人眼感知）
- **兼容**: rgb/hex 格式（向后兼容）
- **UIUXAnalyzer 检测**: 支持 rgb/hex/oklch 三种格式解析

### 1.3 对比度

- **标准**: WCAG 2.1 AA
  - 正常文字: 对比度 ≥ 4.5:1
  - 大文字（≥18pt 或 ≥14pt bold）: 对比度 ≥ 3:1
  - UI 组件: 对比度 ≥ 3:1

---

## 二、间距尺度

### 2.1 4pt 网格系统

- **基准**: 4px
- **语义间距**:

| Token | 值 | 用途 |
|-------|-----|------|
| `xs` | 4px | 紧凑间距（图标与文字） |
| `sm` | 8px | 元素内间距 |
| `md` | 16px | 元素间间距 |
| `lg` | 24px | 区块内间距 |
| `xl` | 32px | 区块间间距 |
| `2xl` | 48px | 大区块间距 |

### 2.2 禁止

- 非 4pt 倍数的间距值（如 7px、13px、21px）
- 负 margin（除特殊布局需求外）

---

## 三、字体策略

### 3.1 字体族

- **禁止过度使用**: Inter / Roboto / DM Sans（AI 前端反模式，过度同质化）
- **推荐**: 根据项目定位选择有辨识度的字体组合
- **中文**: 系统默认中文字体（苹方/微软雅黑/思源黑体）

### 3.2 字号层级

| 层级 | 字号 | 行高 | 用途 |
|------|------|------|------|
| H1 | 32px | 1.25 | 页面标题 |
| H2 | 24px | 1.3 | 区块标题 |
| H3 | 20px | 1.35 | 子区块标题 |
| Body | 16px | 1.5 | 正文 |
| Small | 14px | 1.4 | 辅助文字 |
| Caption | 12px | 1.3 | 标注/脚注 |

### 3.3 禁止

- font-size < 12px（可读性差）
- line-height < 1.2（行距过窄）
- 同一页面超过 4 种字重组合

---

## 四、动效约束

### 4.1 允许

- `transform` 动画（translate/scale/rotate）
- `opacity` 动画
- `box-shadow` 动画

### 4.2 禁止

- `width` / `height` 动画（触发重排，性能差）
- `bounce` easing（物理不准确）
- 动画时长 > 1s（用户等待焦虑）
- `backdrop-filter: blur()` 过度使用（glassmorphism overuse，性能差）

### 4.3 推荐缓动函数

- `ease-out`: 元素进入
- `ease-in`: 元素离开
- `ease-in-out`: 状态切换
- 自定义 `cubic-bezier`: 特殊场景

---

## 五、响应式断点

### 5.1 断点定义

| 断点 | 宽度 | 用途 |
|------|------|------|
| `sm` | ≥640px | 手机横屏 |
| `md` | ≥768px | 平板竖屏 |
| `lg` | ≥1024px | 桌面窄屏 |
| `xl` | ≥1280px | 桌面宽屏 |
| `2xl` | ≥1536px | 大屏显示器 |

### 5.2 禁止

- 固定宽度（`width: 800px`）— 不响应式
- 无断点的流式布局 — 大屏拉伸过度
- 水平溢出（`overflow-x: scroll`）— 移动端体验差

---

## 六、交互准则

### 6.1 按钮尺寸

- **最小尺寸**: 44×44px（WCAG 触摸目标）
- **推荐尺寸**: 48×48px（舒适触摸）

### 6.2 状态反馈

- **必须**: hover / focus / active / disabled 四种状态
- **focus outline**: 不可移除（a11y 要求），可用 `:focus-visible` 优化视觉

### 6.3 破坏性操作

- **必须**: 二次确认（如删除、重置）
- **推荐**: 撤销机制（如 toast with undo）

---

## 七、a11y 准则

### 7.1 WCAG 2.1 AA

- 图片必须有 `alt` 属性
- 表单 input 必须有关联 `label`
- `div[role=button]` 必须有键盘交互支持
- 颜色对比度符合 1.3 节标准

### 7.2 语义化 HTML

- 使用语义化标签（`<nav>`/`<main>`/`<article>`/`<section>`）
- 避免滥用 `<div>` 作为通用容器

---

## 八、反模式禁令（Anti-pattern Bans）

来源: taste-skill Anti-pattern Bans

| # | 反模式 | 检测特征 | 严重度 |
|---|--------|----------|--------|
| 1 | border-left accent stripes | `border-left: Npx solid <color>` | warning |
| 2 | gradient text | `background-clip: text` + `gradient` | warning |
| 3 | glassmorphism overuse | `backdrop-filter: blur()` 使用 >2 次 | warning |
| 4 | overused fonts | Inter / Roboto / DM Sans 字体声明 | info |
| 5 | purple-blue gradient | 紫蓝渐变背景 | warning |
| 6 | nested cards | `.card .card` 嵌套 | warning |

---

## 九、UIUXAnalyzer 集成

UIUXAnalyzer 在审计时加载本文件，将上述准则作为项目特定规则注入：

```python
# 伪代码示意
analyzer = UIUXAnalyzer()
analyzer._design_context = load_design_md()  # 加载本文件
# 审计时，规则引擎根据 design_context 调整阈值和检测项
issues = analyzer._rule_engine.check(probes, taste_dials, design_context)
```

---

> **维护规则**: 本文件是活文档，随项目设计演进更新。每次 UI/UX 相关变更必须同步更新本文件。
> **一致性检查**: CI 会检查 DESIGN.md 中的设计准则与 UIUXAnalyzer 规则库的一致性。
