# weekly 设计规范

> 主题：**swiss-ikb**（瑞士国际主义风格 · 克莱因蓝）
>
> 适用：web-video-presentation 技能下的视频演示项目
>
> ⚠️ **weekly 系列固定使用本主题（swiss-ikb / IKB 克莱因蓝），不可切换、不提供其他主题选项。** 所有 weekly 项目（weekly-1/2/3 及以后）一律使用 `tokens.css` 的 IKB 值。


---

## 1. 设计哲学

- **风格源头：** 瑞士国际主义（Swiss International Style），又称瑞士平面风格
- **核心原则：** 越大越细（bigger gets thinner）—— 大尺寸排版使用 Extra-Light（200 weight）字重
- **视觉签名：** 1px 极细网格线（hairline grid）作为舞台背景，是设计师"隐形但可见"的骨架
- **情感气质：** 干净、权威、现代、百科式（encyclopedic）
- **视频第一：** 所有设计决策优先于 1920×1080 录屏场景，而非交互式界面

---

## 2. 色彩体系

| Token | 值 | 用途 |
|-------|-----|------|
| `--shell` | `#e8e8e6` | 舞台外背景（外框） |
| `--surface` | `#fafaf8` | 舞台主表面（画布底色） |
| `--surface-2` | `#f0f0ee` | 次级表面（卡片/面板/引用块/数据标签） |
| `--surface-3` | `#d4d4d2` | 三级表面（用于 hover / active 状态） |
| `--text` | `#0a0a0a` | 主文字色 |
| `--text-2` | `#2a2a2a` | 次级文字色（卡片详情、标签文字） |
| `--text-mute` | `#737373` | 弱化文字色（kicker、副标题） |
| `--text-faint` | `#a8a8a8` | 极弱文字色（仅用于纯装饰性文字） |
| `--rule` | `#e0e0e0` | 分割线/边框色 |
| **`--accent`** | **`#002fa7`** | **IKB 国际克莱因蓝 — 唯一饱和色** |
| `--accent-soft` | `rgba(0,47,167,0.08)` | 克莱因蓝柔化背景（数据高亮、标签底） |
| `--accent-glow` | `rgba(0,47,167,0.35)` | 克莱因蓝发光/阴影 |

### 变体主题（仅改 `--accent` 即可切换）

> ⚠️ 下表仅作**预留参考**。**weekly 系列固定使用 IKB 克莱因蓝**，不选用以下变体。

| 变体 | `--accent` 值 | 备注 |
|------|---------------|------|
| **IKB 克莱因蓝**（默认，weekly 唯一使用） | `#002FA7` | `--accent-on` 白色 |
| 柠檬黄 | `#FFD500` | `--accent-on` 需改为 `#0a0a0a` |
| 柠檬绿 | `#C5E803` | 同上 |
| 安全橙 | `#FF6B35` | 保持白色但字重 ≥ 600 |

---

## 3. 字体体系

### 字体栈

| 角色 | 字体 |
|------|------|
| 中文展示 | `"Noto Sans SC", "Source Han Sans SC", -apple-system, sans-serif` |
| 英文展示 | `"Inter", "Helvetica Neue", "Helvetica", "Arial", sans-serif` |
| 正文 | `"Inter", "Helvetica Neue", "Noto Sans SC", -apple-system, sans-serif` |
| 等宽/标签 | `"JetBrains Mono", "SF Mono", ui-monospace, monospace` |

### 字重规范

| 上下文 | 字重 | 说明 |
|--------|------|------|
| Hero 数字（大号） | **200 (Extra-Light)** | **签名特性** — 越大越细 |
| Mono 标签/kicker | 400–500 (Regular/Medium) | — |
| 正文/卡片描述 | 300 (Light) | 视频中 body 文字偏细更有质感 |
| 强调字重 | 700 (Bold) | 仅用于突出关键词、数据高亮 |

### OpenType 特性

```css
font-feature-settings: "tnum", "ss01", "ss02", "cv02";
```

### 字号层级（视频场景）

> 以下为 **1920×1080 录屏场景**的实测字号区间。视频中文字必须比常规界面大得多
> 才能在 1080p 下清晰可读。所有非 hero 文字在初稿基础上 **统一 +20px** 是常态。

| 上下文 | 实际区间 | 备注 |
|--------|---------|------|
| Hero 大标题（中文） | `clamp(72px, 6.5vw, 120px)` | 章节核心标题、主标语 |
| Kicker / Mono 标签 | `35–38px` | 每章顶部标签，固定值 |
| 英雄数字 | `clamp(96px, 8vw, 144px)` | 统计数据主数字 |
| 次级数字 | `50–56px` | 卡片中的统计数字 |
| 卡片标题 / 名称 | `clamp(44px, 4vw, 72px)` | 实体/产品名称（展示字体） |
| 卡片描述文字 | `36–42px` | 卡片中的详情说明 |
| 标签 / 芯片文字 | `30–36px` | 关键词标签（mono 字体） |
| 正文段落 | `38–48px` | 数据说明、上下文描述 |
| 副标题 / 字幕 | `44–54px` | 主标题下的补充说明 |
| 小标签 / 极弱文字 | 24px 起 | 一般不使用，避免录屏不可读 |

**经验法则**：视频口播稿每步 ~120 字（均值），屏幕文字宜少不宜多。
一段口播对应一个聚焦的想法，屏幕只展示一个视觉焦点。

**base.css 默认字号在视频中的覆盖**：base.css 的 `.kicker`（13px）和 `.masthead`（brand 22px / issue 11px）按交互界面设计，录屏 1080p 下不可读。每个章节必须用 `.xx-scene .masthead .brand { font-size: 34px }` / `.issue { font-size: 26px }` 覆盖放大，kicker 通过章节级 `.xx-kicker` 覆盖到 **30px**（letter-spacing 0.18–0.2em，`--accent` 色）。这些覆盖是常例而非可选项。

---

## 4. 版式布局

### 舞台规格

| 属性 | 值 |
|------|-----|
| 分辨率 | **1920 × 1080**（16:9） |
| 缩放方式 | CSS transform scale 保持比例居中 |
| 内边距 | `--stage-pad-x: 96px` / `--stage-pad-y: 72px` |
| 圆角 | `--r-stage: 0`（直角） |
| 阴影 | `0 60px 160px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.06)` |

### 场景布局模式

从 weekly-1/2 实践中提炼出两种标准场景布局：

**A. `.scene-pad` 居中布局**
- 全屏居中，flex column + center
- 适用于章节收尾、单一焦点（如法规、金句）
- 无 header/kicker 区域，全屏内容自由分布

**B. `.section` 结构化布局**
- 顶部 `.header` 区域（含 `.kicker` + 可选装饰）
- 中间 `.body` 区域（flex row/column，内容区）
- 底部 footer 区域（quote 或 conclusion）
- 章节专用 CSS 前缀 + 对应命名（如 `.ec-header`、`.ec-section`）
- 适用于信息密集的页面（数据、对比、表格）

### 背景装饰

**1px 极细网格**（瑞士风格签名骨架）：

```css
--surface-pattern:
  linear-gradient(rgba(10,10,10,0.045) 1px, transparent 1px),
  linear-gradient(90deg, rgba(10,10,10,0.045) 1px, transparent 1px);
--surface-pattern-size: 64px 64px;
```

### 卡片（card）

| 属性 | 值 |
|------|-----|
| 圆角 `--r-card` | **0**（直角 — 瑞士风格 = 直接矩形） |
| 边框 | `1px solid var(--rule)`（外框） |
| 背景 | `var(--surface-2)` |

卡片阴影统一用 `<inset 0 0 0 1px var(--rule)>`（内边框）替代外发光，
保持平面风格。

### Chips / Tags

```css
padding: 10–14px 22–24px;
border: 1px solid var(--rule);
font-family: var(--font-mono);
background: var(--surface-2);  /* 可选 */
```

- 用于关键词标签、数据标签、分类标识
- 多个 chip 统一使用 **staggered 动画延迟**（每项间隔 100–150ms）
- 强调项内文字用 `<strong>` + `var(--accent)` 高亮

### 规则分割线

```css
.rule {
  width: 100%; height: 0; border: 0;
  border-top: 1px solid var(--rule);
}
.rule-grow {
  /* 水平伸展动画 */
  transform: scaleX(0); transform-origin: left;
  animation: rule-grow 600ms var(--ease-expo) 100ms forwards;
}
```

### 引用块（Pull-quote）

- 左侧 4px `var(--accent)` 竖线边框
- 背景 `var(--surface-2)`
- 文字使用 var(--font-body) 300 weight
- 强调词用 `var(--accent)`

### VS 对比布局

- 左右两卡片，中间 `.vs-divider` 文字
- 卡片使用 `.card` 基础样式 + 错开动画延迟
- VS 文字使用 `font-display-en` 200 weight，`text-faint` 颜色

### 转变对比（transformation）— 旧 → 新

新闻里"格局变化 / 升级 / 换轨"的统一表达（weekly-3 中 `.aa-shift`、`.pw-shift`、`.cp-compare`、`.rb-progress` 同构）：

- 旧词：`--text-faint` / muted + `text-decoration: line-through`（3px 划线），300 weight
- 箭头：`font-display-en` 200 weight，`--accent`，~60–90px
- 新词：`--accent`，700 weight，比旧词大一号
- 入场顺序：旧词 → 箭头 → 新词，stagger 200–350ms；新词用 stamp 盖章动画收尾
- 适用：赛马→整合、谁更聪明→谁更能干活、稀缺资源→水电、demo→产线

### 整合合并（merger）— A × B → 合并

"两个实体整合成一个"的表达（weekly-3 `.aa-merge`）：

- 两个来源盒子 + `×`（200 weight 灰）→ 箭头 → 一个高亮盒子（`--accent` 边框 + 700 weight）
- 来源盒子：`--surface-2` + 1px 边框，300 weight；产物盒子 `--accent` 边框
- 入场：来源盒错开 200ms → × → 箭头 → 产物盒 stamp
- 适用：飞书 × 豆包 → 整合、产品合并

### 多模态 → 单一输出（pipeline）

"能看懂多类输入 → 产出一件事"的表达（weekly-3 `.rb-modal`）：

- 一行输入块（同构小卡片，各带 stagger）→ `→` 箭头 → 一个 accent 强调的输出块（`--accent` 边框 + `--accent-soft` 底）
- 适用：视频/图像/音频 → 任务规划；多输入 → 单一能力

### Kicker 规范

每章顶部可选 mono 标签：

```css
.kicker {
  font-family: var(--font-mono);
  font-size: 37px;          /* 固定值 */
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent);
  line-height: 1.1;
}
```

---

## 5. 动效系统

### 节奏

| Token | 值 |
|-------|-----|
| `--dur-quick` | 180ms |
| `--dur-base` | 400ms |
| `--dur-slow` | 650ms |
| `--dur-cinematic` | 1000ms |

### 缓动函数

| Token | 值 | 特性 |
|-------|-----|------|
| `--ease-quart` | `cubic-bezier(0.19, 1, 0.22, 1)` | 四阶缓出（默认） |
| `--ease-expo` | `cubic-bezier(0.86, 0, 0.07, 1)` | 指数级缓出（规则生长） |
| `--ease-soft` | `cubic-bezier(0.4, 0, 0.1, 1)` | 柔滑过渡 |
| `--ease-overshoot` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | 带超调的弹入 |

> **Swiss 不是弹簧** — 默认不使用 spring/弹跳动效。使用 `linear` 或 `ease-quart`。

### 核心动画

| 动画名 | 效果 | 适用场景 |
|--------|------|----------|
| `rise-in` | 透明度 0→1 + 位移 24px↑ | 卡片、chip、列表项入场 |
| `fade` | 透明度 0→1 | 辅助元素入场 |
| `scale-punch` | 缩放 0.7→1.02→1（带超调） | 关键数字/强调 moment |
| `scale-x` / `rule-grow` | 水平 0→1 伸展 | 分割线生长 |
| `mask-reveal` | clip-path 从左到右擦出 | 文字揭示 |
| `letter-stagger` | 逐字母上升 + 缩放 | 标题逐字动画（`--i` 控制延迟） |

### 动画延迟设计原则

多元素同时出现时使用 **staggered 延迟**，符合"逐步揭示"原则：

| 元素个数 | 延迟增量 | 示例 |
|----------|---------|------|
| 2–3 个卡片 | 200–300ms | `.card:nth-child(1) { animation-delay: 200ms; }` |
| 3–5 个 chip | 100–150ms | `.chip:nth-child(2) { animation-delay: 550ms; }` |
| 标签/辅助文字 | 150–250ms | 在主内容出现后跟进 |

**注意**：当列表元素被非同类元素交叉隔开时，使用 `nth-of-type` 替代
`nth-child`。详见反模式章节。

---

## 6. UI 组件规范

### 组件列表

| 组件 | 用途 |
|------|------|
| **Stage** | 16:9 舞台容器，点击任意位置前进 step |
| **ProgressBar** | 底部章节/步骤进度条 |
| **AutoToggle** | 手动/自动模式切换 |
| **AutoStartGate** | 自动模式启动门 |
| **MaskReveal** | clip-path 文字擦出动画 |

### 通用类名

| 类名 | 用途 |
|------|------|
| `.scene` | 每章根容器（绝对定位，撑满舞台） |
| `.scene-pad` | 带内边距的居中布局容器 |
| `.hero-num` | 大号数字（使用英文展示字体 + 超细字重） |
| `.kicker` / `.label-mono` | 章节标签（mono 37px 大写） |
| `.rule` | 极细分割线（1px solid） |
| `.rule-accent` | 蓝色强调分割线（2px solid） |
| `.card` | 卡片容器（直角 + 1px 边框 + surface-2 背景） |
| `.chip` | 标签式长方形元素（bordered + mono + staggered） |
| `.badge-mono` | 药丸标签（mono 大写） |
| `.badge-mono.is-accent` | 蓝色强调药丸标签 |
| `.pull-quote` | 左边框引用块（4px 蓝色边框 + surface-2 背景） |
| `.stat-row` | 统计数字行（flex row + 多个 stat-card） |
| `.stat-card` | 统计卡片（大数字 + 标签 + 1px 边框） |
| `.vs-divider` | 对比分隔标识（两端卡片中间 vs） |
| `.data-display` | 数据展示区（大数字 + 描述文字） |
| `.dot-accent` | 蓝色状态圆点（7px，`var(--accent)` 填充） |
| `.corner-mark` | 左上角注册标记（胶片风格） |
| `.click-cue` | 右下角点击提示 |
| `.masthead` | 杂志刊头布局 |

---

## 7. Hero 数字系统

Hero 数字（统计数据、年份、关键数字）使用独立 token 控制：

```css
--hero-num-font: var(--font-display-en);    /* 使用英文展示字体 */
--hero-num-weight: 200;                      /* Extra-Light — 越大越细 */
--hero-num-track: -0.03em;                   /* 紧缩字距 */
```

大小区间：
- 主数字：`clamp(96px, 8vw, 144px)`（单独占据一行）
- 次级数字：`50–56px`（用于 stat-card 内）
- 超大 hero：`clamp(140px, 11vw, 200px)`（全书第一屏的数字）

注意：数字使用 `tnum`（tabular numbers）确保等宽对齐。
不要使用 emoji 替代数字。

---

## 8. 各章节 CSS 前缀命名

| 章节 | 前缀 | 文件 |
|------|------|------|
| Coldopen（开篇） | `.co-` | `Coldopen.css` |
| China Waves（中国） | `.cw-` | `ChinaWaves.css` |
| Overseas（海外） | `.ov-` | `Overseas.css` |
| Ecosystem（产业） | `.ec-` | `Ecosystem.css` |

**新闻周报结构**（weekly-3 起，7 章制）——数字前缀 + 章节 id 首字母：

| 章节 | 前缀 | 文件 |
|------|------|------|
| coldopen（开篇） | `.co-` | `Coldopen.css` |
| llm-release（大模型开源） | `.lr-` | `LlmRelease.css` |
| agent-app（Agent 入口） | `.aa-` | `AgentApp.css` |
| price-war（推理成本/价格战） | `.pw-` | `PriceWar.css` |
| safety-governance（安全治理） | `.sg-` | `SafetyGovernance.css` |
| robotics（具身智能） | `.rb-` | `Robotics.css` |
| compute（算力） | `.cp-` | `Compute.css` |

所有章节内定义的 keyframes 也使用对应前缀命名（如 `co-rise-in`、`ec-fade`）。

**新增章节**按数字序号递增前缀：`05-xxx → .xx-`（章节 id 首字母）。

---

## 9. narrations.ts 编码规约

### 避免中文引号解析错误

`narrations.ts` 是 step 数和音频合成的唯一真相源。
JS/TS 字符串中如果包含中文双引号 `"` `"`，在双引号字符串中会被
解析器误认为字符串结束：

```typescript
// ❌ 错误 — 中文 " 会提前结束字符串
const narrations = [
  "行业共识：AI 从"拼谁参数大"，变成了"拼基础设施硬"。",
];

// ✓ 正确 — 使用模板字面量
const narrations = [
  `行业共识：AI 从"拼谁参数大"，变成了"拼基础设施硬"。`,
];
```

### 换行符处理

口播文本中的 `\n`（换行）会被 JSON 保留。当口播需要在长段落中
自然分气口时，可以在模板字面量中保留换行：

```typescript
`转海外。知名分析机构 SemiAnalysis 出了份报告——
现在 AI 圈是双雄争霸，OpenAI 和 Anthropic 两家领跑。
谷歌因为算力锁定加战略失误，直接掉到第五。`
```

### 字数控制

单步口播建议在 **60–250 字** 之间（实测均值约 124 字）。
超过 250 字建议拆分为两个 step。

---

## 10. CSS 动画反模式

### nth-child vs nth-of-type

当列表元素被非同类元素穿插时，**始终使用 `nth-of-type` 而非 `nth-child`**：

```css
/* ❌ 错误 — 如果元素被其他类型穿插，nth-child 选中错误元素 */
.item:nth-child(2) { animation-delay: 200ms; }

/* ✓ 正确 — 只计数同类型元素 */
.item:nth-of-type(2) { animation-delay: 200ms; }
```

典型场景：流程图中的节点和箭头交替排列，此时 `.node:nth-of-type(N)`
正确选中所有节点，而 `.node:nth-child(N)` 则被箭头打乱。

---

## 11. 设计资产规范

### 视频结构（模板）

| 章节 | 步骤数参考 | 内容 |
|------|-----------|------|
| Coldopen（开篇） | 4–6 | 头条新闻钩子 + 核心议题 |
| China Waves（国产动态） | 3–5 | 中国大模型/产品发布 |
| Overseas（海外格局） | 3–5 | 海外巨头新闻/分析 |
| Ecosystem（产业与政策） | 4–6 | 政策、标准、数据、总结 |

总步骤控制 16–22 步，总时长约 3–5 分钟。

**新闻周报结构变体**（weekly-3 起，主题不固定、逐周换题材时用）——「冷开场 + 6 个主题章」，每章 3–4 步：

| 章节 | 步骤数参考 | 内容 |
|------|-----------|------|
| coldopen（开篇） | 3 | 本周头条 + 1~2 个钩子数据 |
| 主题章 × 6（如 大模型/Agent/价格战/安全/具身/算力） | 各 3–4 | 每章一个聚焦信号，最后一步收束 |

总步骤 21 步、口播 ~790 字、总时长 ~3:15。章节名按当周实际议题定，前缀仍按「id 首字母」规则。

### outline 结构约定（weekly-3 起）

`outline.md` 每章固定四块，格式为：

1. **引言行**——`> **主题**：`（swiss-ikb / Checkpoint 确认）+ `总时长` + `章节数 / 总步数`
2. **信息池**——每章开头的 block，逐条列出本章要用的**事实 + 数字 + 引用**，**每条必带来源标注**（`—— 来源 article §章节`），供章节实现时"按需挂角标/副标/pull-quote/mono cue"
3. **开发计划**——按 step 列出**单一句屏幕内容描述**（`step N (~Ts) — 视觉内容`），**不写动画行/毫秒**（动画由实现时按 PRINCIPLES + ANTI-AI 即时设计）
4. 全文末尾附**素材清单**（每章 ✓/⚠️/--）与**自检清单**（step 单一句、时长累加误差 <10%、信息池每条带来源等）

口播稿 `script.md` 用 `---` 按 step 切分，与 narrations.ts 一一对应。

### 音频规范

- **推荐 TTS provider: edge-tts**（免费，零配置，中文音色好）
  - 安装：`pip install edge-tts`
  - 默认音色：`zh-CN-XiaoxiaoNeural`（晓晓 · 女声 · 清脆、明亮、标准）
  - 合成速度：1.2 倍（`--rate=+20%`）
  - 备选：`zh-CN-YunxiNeural`（男声）
  - 使用 `--file` 参数传递文本避免 shell 转义问题
- 音频文件路径：`/audio/<chapter-id>/<step>.mp3`
- 文件名 1-indexed（与 extract-narrations 脚本输出一致）
- 自动模式：音频播放完毕 → auto-advance
- 无音频时回退：按 250ms/字 估算时长

### 素材清单格式

```
- [✓/⚠️/--] 素材名（来源说明）
```

- `✓` = 已有
- `⚠️` = 待提供
- `--` = AI 生成（placeholder）

---

## 12. 反模式（禁止项）

- ❌ 不使用圆角（`--r-card: 0`，瑞士风格 = 直接矩形）
- ❌ 不使用弹跳/spring 缓动（瑞士风格不是弹簧）
- ❌ 不使用衬线字体（Swiss = 无衬线）
- ❌ 不使用渐变或阴影（平面 + 1px 边框）
- ❌ 不使用 emoji
- ❌ 不用硬编码字体系列（使用 token）
- ❌ 不在一行中使用同级卡片 + 交错 `nth-child` 延迟（用 `nth-of-type`）
- ❌ 不在双引号字符串中使用中文引号（用模板字面量）
- ❌ 不跨章节共享 CSS 类名前缀（每章独立 `.xx-` 前缀）
- ❌ 不在同一屏中用同步 stagger 展示 N 项内容（1 项 = 1 step）

---

## 13. 变体切换

> ⚠️ **weekly 系列固定使用 IKB 克莱因蓝，不做变体切换。** 本段仅说明机制，供 weekly 以外的项目使用。

在同一套 CSS 结构下，仅通过修改 `tokens.css` 中的 `--accent` 变量即
可切换 4 种瑞士风格变体：

- **IKB 克莱因蓝** `#002FA7`（默认，weekly 系列唯一使用）
- **柠檬黄** `#FFD500`（需改 `--accent-on`）
- **柠檬绿** `#C5E803`（同上）
- **安全橙** `#FF6B35`（保持白色字重 ≥ 600）

**新开 weekly 项目时**：直接复用 weekly-3 的 `presentation/` 脚手架（含 `tokens.css` 的 IKB 值、`.theme` = `swiss-ikb`、fonts/animations/base），不提供主题选择。

---

## 14. 开发注意点

### Step 数一致性

`narrations.ts` 数组长度 = 章节 step 总数。`.tsx` 中 `switch(step)`
的分支数必须匹配。通过 `chapters.ts` 注册时自动关联。

### STORAGE_KEY Bump

任何章节结构变动（增/删/重排章节，改变某章 narrations 长度）后，
更新 `useStepper.ts` 的 `STORAGE_KEY`（如 `v8` → `v9`），防止持久化
游标落到不存在的位置。

### 每个 step 独占整屏

每个 step 设计为一个独立的聚焦想法，`if (step === N) return <SceneN />`。
没有分页、滚动、弹窗。

### 口播节拍 = step 边界

音频不能跨 step 播放。口播稿中一个自然段落对应一个 step。
长段落按语义气口拆成多个 step。

### 章节文件结构与组件模板

每章目录固定三文件：`<NN>-<id>/<Name>.tsx`、`<Name>.css`、`narrations.ts`。`.tsx` 顶层 `import "./<Name>.css"`，组件模板：

```tsx
/* 每步一个子组件函数 */
function Step0() { return <div className="xx-scene scene-pad xx-center">…</div>; }
function Step1() { … }

export default function Chapter({ step }: ChapterStepProps) {
  switch (step) {
    case 0: return <Step0 />;
    case 1: return <Step1 />;
    default: return null;
  }
}
```

- 场景根元素固定组合 `scene-pad`（排版）或 `scene-pad xx-center`（居中）——不要用 `.scene`（registry 已包一层）
- 视觉样式全部放 `<Name>.css`，类名 + keyframes 全用章节前缀
- **禁止**在 `.tsx` 里写 inline `style` 承载视觉（仅容器 flex 微调可容忍）

### Spacing token 白名单

`base.css` 只定义 `--space-2/3/4/5/7/9`（8/12/16/24/48/96px）。**没有 `--space-6`**。章节 CSS 中 `var(--space-6)` 会解析失败 → 该属性静默回退为初始值。用 spacing token 前先确认已定义；需要 32px 档位时直接写硬值或改用 `--space-5`/`--space-7`。
