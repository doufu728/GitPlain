---
version: alpha
name: GitPlain
description: A quiet, bright catalog for people who do not write code. Think Apple's product pages crossed with Airbnb's card grid — a white canvas, one blue accent, softly rounded cards, and nothing decorative between the reader and the project. The chrome disappears; the cards carry everything. No gradients, no glow, no colored backgrounds, no shadow stacking. If a visual element does not help the reader decide which project to open, it does not exist.

colors:
  # 唯一强调色（只用于链接、主按钮、选中态）
  primary: "#0066cc"
  primary-hover: "#0071e3"
  # 文字
  ink: "#1d1d1f"          # 主文字（标题、项目名）
  ink-muted: "#6e6e73"    # 次要文字（描述、适合谁）
  ink-faint: "#86868b"    # 最弱文字（更新时间、星数标签）
  # 背景
  canvas: "#ffffff"       # 页面底色
  canvas-alt: "#f5f5f7"   # 分组之间的浅灰底（可选）
  card: "#ffffff"         # 卡片底色（与页面同色，靠边框区分）
  # 线条
  hairline: "#e8e8ed"     # 卡片边框、分割线
  # 星数/热度用色（唯一的"暖"色，克制使用）
  star: "#f5a623"

typography:
  # 全部走系统字体栈，不引外部字体（中英文都要好看）
  font-stack: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif"

  page-title:
    fontSize: 34px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.4px
  section-title:
    fontSize: 21px
    fontWeight: 600
    lineHeight: 1.3
  card-title:            # 项目名 repo 全名
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.35
  card-desc:             # 一句话人话解释
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
  card-meta:             # 适合谁 / 更新时间
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  number:                # 星数等数字
    fontSize: 13px
    fontWeight: 600
    fontVariantNumeric: tabular-nums

rounded:
  sm: 8px        # 小标签、按钮
  md: 14px       # 卡片主圆角（这是全站最重要的一个数）
  lg: 20px       # 大的容器/分组
  full: 9999px   # 胶囊标签

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  page-max-width: 720px    # 单列最大宽度（手机上就是 100% - 32px）
  card-padding: 20px
  card-gap: 12px

elevation:
  # 全站只有两级高度，且都极轻
  card-rest: "none"                              # 静止不用阴影，靠 hairline 边框
  card-hover: "0 4px 16px rgba(0, 0, 0, 0.06)"    # hover 才轻微抬起
  # ponytail: 就这两级，不要加更多
---

# GitPlain · 视觉规范

## 这个页面是什么

给**不懂编程、但开始用 AI 的人**看的 GitHub 项目榜单。
读者的问题是「**我该用哪个**」，不是「这个代码怎么写的」。

所以页面的唯一任务：**让 14 张卡片在 3 秒内被扫完，并让人想点开其中一个。**

## 三条不可违反的原则

### 1. 外壳消失，内容浮现

抄 Apple 的一句原话：
> "the wall disappears and the artifact takes over"（墙消失，展品浮现）

**翻译成可执行的话：**
- 页面背景是纯白，不要有背景图案、纹理、色块
- 卡片不加阴影（静止时），只用 1px `hairline` 边框
- 不要在卡片外面再套一层带背景的容器（**禁止卡片嵌卡片**）
- 除了卡片之间的间距，页面上不要有其他装饰性元素

### 2. 一个强调色，就一个

- 全站只有一个蓝色 `#0066cc`
- **只用在**：主按钮、可点击的链接文字、筛选选中态
- **不许用在**：背景、标题、边框、图标填充、进度环以外的任何地方
- 星数用 `star` 那个橙色，**只是很小的数字旁边的图标**，不是大面积色块

### 3. 圆角、间距、字号，只用上面定义过的值

不许出现 `border-radius: 6px` 这种"随手写的"值。
卡片就是 `14px`，标签就是 `9999px`（胶囊），按钮就是 `8px`。

---

## 明确的禁则（违反任何一条都算不合格）

| # | 禁止 | 为什么 |
|---|---|---|
| 1 | **任何线性/径向渐变** | Apple 全站零渐变 token，这是"AI 味"第一来源 |
| 2 | **渐变文字**（`background-clip: text`） | 同上 |
| 3 | **卡片嵌卡片**（卡片里再套一个带背景的盒子） | 层级混乱，读者不知道该看哪 |
| 4 | **彩色背景 + 灰字** | 对比度不足，小白看不清 |
| 5 | **标题上方的小圆角图标块**（AI 生成站点的标配） | 一眼假 |
| 6 | **卡片圆角 > 16px** | 太圆会显得像玩具，不是工具 |
| 7 | **多层 `box-shadow` 叠加** | 全站最多一层，且只在 hover |
| 8 | **彩色发光边框 / 霓虹效果** | 和"安静"的定位冲突 |
| 9 | **超过 2 种字重混用** | 只用 400 和 600 两种 |
| 10 | **首屏需要一个"解释这个网站是干什么的"大标题段** | 标题一行就够，读者要的是列表不是介绍 |

---

## 卡片内部的信息层级（从上到下）

```
┌────────────────────────────────────────┐
│  [分类标签胶囊]              [+12,838/周]  │  ← 13px，标签用浅灰底，涨幅用 star 色
│                                        │
│  cloudflare / security-audit-skill     │  ← 17px / 600，ink
│                                        │
│  给 AI 编程助手用的安全检查工具，        │  ← 15px / 400，ink-muted
│  在它改代码之前先扫一遍有没有漏洞。      │
│                                        │
│  适合：用 Claude Code / Cursor 写代码，  │  ← 13px，ink-faint
│        担心 AI 改出安全问题的人          │
│                                        │
│  ★ 54,972                    [去看看 →] │  ← 13px 数字 + 主按钮
└────────────────────────────────────────┘
```

**层级原则：**
- **项目名最大最黑**（读者先看到它）
- **一句话解释第二重要**（决定要不要点）
- **「适合谁」是辅助**（确认"这是给我的吗"）
- **星数是佐证，不是主角**（所以数字比描述小）
- **按钮在最右或最下**，颜色用 `primary`

---

## 交互的视觉要求

| 交互 | 视觉要求 |
|---|---|
| **收藏按钮反馈** | 按钮收缩成圆形 → 对勾描边画出（`stroke-dasharray`）→ 3-5 个粒子向外散去。**总时长 ≤ 600ms**，不要拖沓 |
| **筛选联动** | 结果数字用滚动动画（类似老虎机），进度环用 `stroke-dashoffset`。**选中的胶囊标签**：底变 `primary`，字变白 |
| **圆形扩散转场** | 从**点击位置**向外扩散（不是从屏幕中心）。用 `clip-path: circle(0 at Xpx Ypx)` → `circle(150% at Xpx Ypx)`。**≤ 500ms** |

**动效共同原则：快、轻、不抢戏。**
动画是"确认操作发生了"，不是"表演"。任何超过 800ms 的动画都是错的。

---

## 响应式（只有一个断点）

- **≥ 640px**：单列，最大宽度 720px，居中
- **< 640px**：单列，左右各留 16px 边距

**不做多列网格。** 14 张卡片单列滚动就够，多列会让小白不知道从哪看起。

**硬性要求：375px 宽度下不能出现横向滚动条。**
最长的 repo 名（如 `multica-ai/andrej-karpathy-skills`）必须能用 `word-break` 或 `overflow-wrap` 处理。

---

## 参考来源

本文件提炼自：
- `VoltAgent/awesome-design-md` 的 **apple** 规范（配色 `#0066cc` / `#1d1d1f` / `#f5f5f7`，无渐变哲学）— 124,815⭐
- 同仓库的 **airbnb** 规范（卡片圆角 14px、白画布、留白优先）

原始文件在 `ref/apple-DESIGN.md` 和 `ref/airbnb-DESIGN.md`，需要更多细节可以查，但**不要整体照搬**——Apple 那套是"大图产品展示"，我们是"卡片列表"，只抄骨架不抄皮肤。

## 颜色可读性（2026-11-02 定案，别再提）

impeccable 检测器报 `#f5a623` 金色对比度仅 2.03:1（WCAG AA 要 4.5:1）。**已试改深一次，用户否决「太丑」，还原。**

规则：
- `--star: #f5a623` **保持亮金**，不为合规改深
- `--ink-faint: #86868b` **保持浅灰**，不为合规改深
- 对比度类告警一律视为已知取舍，不改

理由：这是给国内非程序员看的网站，视觉吸引力 > WCAG 合规。且金色是「增长」的语义色，变深就失去意义。
