---
name: aivedio-video
description: AiVedio 项目专属 skill —— 把每周 AI 新闻周报（.webfetch/*.md / 51ai / 36kr 周报 / 用户丢来的资讯链接）做成 16:9 "网页视频"，或给 weekly 视频出字幕。**三个强触发簇，别漏**：(1) 做视频 —— 用户说"做这周的 AI 新闻视频 / 新一期 weekly 周报 / 周报网页视频 / 把周报素材做成网页视频 / 按项目习惯、老规矩、套路做 / 用 swiss-ikb 克莱因蓝那套做 / 这期 weekly 开始做"，一律走本 skill；(2) 字幕 —— 用户说"加字幕 / 生成字幕 / 字幕还没做 / 出 srt/vtt/lrc 三份 / 按句子级时间轴 / 口播稿改了重出字幕"，也用本 skill 的 scripts/gen-subtitles.py；(3) 封面 / 配图 —— 用户说"做封面 / 出缩略图 / 生成视频封面 / 加张配图"，调用兄弟 skill aivedio-cover（`.claude/skills/aivedio-cover/`）出图，风格锁 references/weekly-cover-design.md。它固化项目层约定：weekly 系列固定 swiss-ikb（IKB 克莱因蓝）主题不可换、7 章制 outline（每章信息池必带来源标注）、edge-tts 口播、narrations.ts 单一真相源、句子级字幕、tsc/build/vite 验证闭环、设计权威源 references/weekly-design-spec.md。**排除**：素材是普通口播稿/文章（非 AI 新闻周报）或用户要自定义主题，退回 /web-video-presentation 通用流程，不用本 skill。
---

# AiVedio 每周 AI 新闻视频 —— 项目生成习惯

本项目用 `/web-video-presentation` 的方法论生成 16:9 "看起来像视频"的网页演示。
本 skill 把项目反复沉淀的习惯固化成标准流程，并把脚手架全套（scaffold.sh + templates + swiss-ikb 主题 + edge-tts adapter）**vendored 进本 skill**，开箱即用、不依赖外部安装。**凡是新开 weekly 视频一律走本 skill。**

## 何时触发 / 何时不用

**触发**：用户说"做这周的 AI 新闻视频 / 新一期 weekly 周报 / 把周报素材做成网页视频 / 用项目习惯生成视频"；或给出 `.webfetch/` 素材、本周 AI 资讯链接。

**不用**：素材是普通口播稿/文章（非 AI 新闻周报），或用户明确要别的主题风格 —— 退回 base skill `/web-video-presentation`。

**封面 / 配图**：用户说"做封面 / 出缩略图 / 生成视频封面 / 加张配图"—— 同样走本 skill，用兄弟 skill **aivedio-cover**（`.claude/skills/aivedio-cover/`）出图（见下「封面 / 配图生成」节），封面风格锁 `references/weekly-cover-design.md`。

---

## 项目目录约定

```
AiVedio/
├── .webfetch/                 # 网页抓取的周报原始素材（.md）
├── weekly/
│   └── weekly-N/               # 每周一个新项目
│       ├── article.md          # 整理后的周报原文（不删）
│       ├── script.md           # 口播稿（--- 分步）
│       ├── outline.md          # 开发计划
│       └── presentation/       # Vite+React+TS 脚手架
└── .claude/skills/<本 skill>/           # 本 skill 所在（自包含，含脚手架全套）
    ├── SKILL.md                # 本 skill 主文件
    ├── README.md               # 人类可读说明
    ├── references/             # ★ 设计规范权威源
    │   ├── weekly-design-spec.md   # swiss-ikb 设计圣经
    │   └── weekly-cover-design.md  # 视频封面设计规范（3:4）
    ├── scripts/
    │   ├── scaffold.sh         # ★ 脚手架（vendored + 适配：锁定 swiss-ikb / 默认 edge-tts）
    │   ├── gen-subtitles.py    # 句子级字幕生成（srt/vtt/lrc）
    │   └── tts-providers/
    │       └── edge-tts.sh     # edge-tts adapter（scaffold 自动拷进项目）
    ├── templates/              # ★ 脚手架模板（vendored：App / useStepper / 组件 / 样式 / 音频管线）
    ├── themes/
    │   └── swiss-ikb/          # ★ 唯一主题（tokens.css + theme.json），锁定
    └── ../aivedio-cover/         # ★ 兄弟 skill：图像生成（封面 / 配图），独立可调用
        ├── SKILL.md            # aivedio-cover 主文件（A/B/C 三模式 + 80+ 模板索引）
        ├── scripts/            # check-mode / generate / edit（node）
        └── references/         # 18 大类结构化 prompt 模板
```

每期在 `weekly/` 下新建 `weekly-<N>`（编号接续现有周次）。

---

## 工作流（本 skill 自包含，直接按此执行）

### Phase 0 —— 素材 → article.md

1. 从用户给的链接抓取周报素材（firecrawl / WebFetch / curl），存 `.webfetch/`。
2. 整理成结构化 `article.md`：
   - 顶部：`# 标题` + 日期范围 + **本周概览**（新闻条数 / 核心信号数 / 关键数字）
   - 主体按主题分节：`## 🧠 大模型 / 💰 价格战 / ⚡ 算力 / 🤝 Agent / 🤖 具身 / 🔒 治理 / 💼 投融资`
   - 每条新闻格式：
     ```
     ### 日期 · 公司 | 一句话标题
     - 要点事实
     - 要点事实
     🔗 来源：XXX
     ```
   - 末尾附来源 URL

### Phase 1 —— 一次产出 script.md + outline.md

**script.md（口播稿）**：
- 用 `---` 分隔每个口播节拍，**一个节拍 = 一个 step**，与 narrations.ts 一一对应
- 只含可念出口的内容，**不写标题、序号、注释**；一律**全角中文标点**（`，` `。` `：` `——` `？` `！`），禁止半角 `,` `:` `?`（半角会破坏字幕切句）
- 一个节拍可装 2~3 句，句间可用空行分段（写进 narrations 仍是同一个字符串；字幕阶段先按空行切段、再按 `。！？` 逐句成 cue，互不合并）
- 总量基准：**7 章 / ~21–22 步 / ~680–800 字 / ~2:30–3:00**（4 字/秒估算；新闻语速更快）
- 周报口播是**短句节拍**：单步 ~30–90 字（比通用网页视频的口语化长句更短 —— 新闻语速快、一步一聚焦；实测 weekly-4 21 步共 680 字，均值 ~32 字/步）。超过 ~90 字按语义气口拆 step

**outline.md（7 章制，每章固定四块）**：

1. **引言行**：`> **主题**：`swiss-ikb`（瑞士克莱因蓝…沿用 weekly 系列 weekly-design-spec.md）` + 总时长 + 章节数/步数
2. **信息池**：每章开头 block，逐条列事实/数字/引用，**每条必带来源标注** `—— 来源 article §章节`（至少 3 条），供实现时"按需挂角标/副标/pull-quote/mono cue"
3. **开发计划**：每步一行 `step N (~Ts) — 单一句屏幕内容描述`。**不写动画、不写毫秒** —— 动画由实现时按 PRINCIPLES + ANTI-AI 即时设计
4. 末尾：**素材清单**（每章 ✓/⚠️/--）+ **自检清单**（step 单一句、时长累加误差 <10%、信息池带来源等）

章节划分参考（7 章制）：coldopen（本周头条 3 步）+ 主题章 ×6（大模型/价格战/算力/终端/治理/收尾，各 3–4 步）。章节 id 与顺序按当周实际议题定，前缀按「id 首字母」规则。

### Checkpoint Plan —— 对齐但主题锁死

写完 script/outline 后停下，让用户一次对齐（稿子 / outline / 素材 / 开发模式）。
**主题不提供选择**：weekly 系列固定 `swiss-ikb`，复用 `references/weekly-design-spec.md`。
开发模式推荐 A（逐章确认）。

### Phase 2 —— 脚手架 + 章节开发

```bash
bash <本 skill>/scripts/scaffold.sh ./presentation
# scaffold.sh + templates + swiss-ikb 主题 + edge-tts adapter 都已 vendored 在本 skill 内，
# 无需安装 base skill，也无需传 --theme（swiss-ikb 是唯一主题，天然锁定）
```

- 第 1 章在主线程完整实现 + 用户验收（**强制 anchor 硬节点，不可跳过**）
- 第 2~N 章按选定模式（A 逐章 / B 顺序 / C 并行 ≤3）
- 每章实现完走完工自检（见设计规范与反模式）

### Phase 3 —— 音频合成（edge-tts）

```bash
npm run extract-narrations                    # 扫 narrations.ts → audio-segments.json
npm run synthesize-audio                      # scaffold 已把 edge-tts 设为默认 provider
```

- edge-tts：免费、零配置、中文音色好。默认音色 `zh-CN-XiaoxiaoNeural`（晓晓·女声），备选 `zh-CN-YunxiNeural`（男声）用 `PRESENTATION_TTS_VOICE=...` 切换；合成速度 `--rate=+20%`；用 `--file` 传文本防 shell 转义
- adapter 已 vendored：本 skill `scripts/tts-providers/edge-tts.sh`，scaffold 自动拷进项目，无需手动 cp
- 音频文件 `public/audio/<id>/<N>.mp3`，**1-indexed**（与 extract-narrations 输出一致）
- 自动模式：音频播完 → auto-advance；无音频回退 `max(1500, len×250)ms` 估算

**字幕（句子级时间轴，weekly 系列）**：
- 字幕按**句子级时间轴**：先按空行切段落、再按 `。！？` 切句（标点留在句末），**每句独立一条带起止时间的 cue**，不把同一步的多句话合并成一个时间块 —— 方便逐句对应口播进度，剪映 / CapCut 可直接导入
- 时间轴规则（对齐运行时真实播放）：每 step 用 mutagen 读 `public/audio/<id>/<N>.mp3` 真实时长（缺音频回退 `len×0.25`s）；段内多句按**字数比例**分配该段时长；**段间加 `0.2s` 间隔**（= `src/App.tsx` 的 `trailMs: 200`，auto 模式播完后的停顿）
- 输出 `public/subtitles.srt` + `.vtt` + `.lrc`（UTF-8），一次生成三份同步更新；依赖 `pip install mutagen`
- 脚本已入库本 skill `scripts/gen-subtitles.py`，路径按脚本位置自动推导、**无需改路径**：
  ```bash
  python scripts/gen-subtitles.py                       # 项目内跑（根 = 脚本上级目录）
  python <skill>/scripts/gen-subtitles.py --project .   # 从 skill 调用，--project 指向 presentation 目录
  ```
- 生成后自检：cue 数 ≈ 各 step 句子数之和；末条结束时间 ≈ 各 mp3 时长累加 + 段间间隔；段内句子起止连续、无重叠、无内嵌空行破坏 cue 块

### Phase 4 —— 验证 + 录屏

```bash
npx tsc -p tsconfig.app.json --noEmit   # 类型检查
npm run build
npx vite                                # dev server localhost:5173（占用时 5174）
```

在浏览器实测 golden path + 边缘情况（自动/手动模式切换、音频推进、进度条悬浮出现）。

---

## 封面 / 配图生成（aivedio-cover，兄弟 skill）

weekly 系列的封面（B 站 / 小红书 3:4 封面、分享缩略图）用**兄弟 skill aivedio-cover**出图：`.claude/skills/aivedio-cover/`。它是独立可调用的 skill，自带完整 SKILL.md 与脚本（check-mode / generate / edit），内部含 weekly 集成节（锁定 `../aivedio-video/references/weekly-cover-design.md`）。封面风格权威源是本 skill 的 `references/weekly-cover-design.md` —— 纯色净暖白底 + 克莱因蓝几何元素 + 超细无衬线排版，**无照片 / 渐变 / 阴影 / 圆角 / emoji**。路径约定：命令里 `<g>` = `.claude/skills/aivedio-cover`（相对项目根）。

**流程**：

1. **定位任务**：封面（3:4，`1080×1440`）还是配图（16:9 等其它比例）。封面直接套 `weekly-cover-design.md` 的 Prompt 模板，仅替换 `[主标题]` / `[副标题]` 占位符（主标题 = 当期主题，副标题 = 如 `2026 W<NN>`）。
2. **定模式**：先跑 `node <g>/scripts/check-mode.js` 确定 A / B / C —— A=Garden 本地出图（需 `ENABLE_GARDEN_IMAGEGEN` + `OPENAI_API_KEY`）；B=交宿主图像工具；C=纯 prompt 顾问。
3. **渲染 prompt**：填好封面模板占位符；如需更丰富画面，再读 `<g>/references/` 里最贴近的模板（如 `poster-and-campaigns/`）补充细节，但**必须守住 swiss-ikb 约束**（无渐变 / 阴影 / 圆角 / 照片 / emoji）。
4. **出图**：
   - Mode A：`node <g>/scripts/generate.js --prompt "…" --size 1080x1440 --image weekly/weekly-<N>/cover.png --prompt-output weekly/weekly-<N>/cover-prompt.md`
   - Mode B：把渲染好的 prompt 交给宿主自带的图像工具。
   - Mode C：保存 prompt 给用户，让他拿去执行（明确告知未出图）。
5. **落盘位置**：图片 `weekly/weekly-<N>/cover.png`；prompt 副本 `weekly/weekly-<N>/cover-prompt.md`（用 `--prompt-output` 归档，便于复用与版本管理）。脚本默认目录 `garden-aivedio-cover/` 相对当前工作区，可被上述显式路径覆盖。
6. **收尾**：一句话告诉用户当前模式、prompt 落点、图落点。

---

## swiss-ikb 设计规范

> **权威源：本 skill `references/weekly-design-spec.md`。写每章前回看核心约束。** 下面是速查摘要。

### 关键 tokens

| Token | 值 | 说明 |
|---|---|---|
| `--accent` | `#002FA7` | IKB 克莱因蓝 —— 唯一饱和色 |
| `--surface` / `--surface-2` | `#fafaf8` / `#f0f0ee` | 净暖白画布 / 次级卡片 |
| `--text` / `--text-mute` | `#0a0a0a` / `#737373` | 主文字 / 弱化文字 |
| `--rule` | `#e0e0e0` | 分割线/边框 |

- 无渐变 / 无阴影 / 无圆角（`--r-card: 0` 直角）
- 1px hairline 极细网格背景（`--surface-pattern` 64px）
- 字体：中文 `Noto Sans SC` / 英文 `Inter` / mono `JetBrains Mono`；大数字用 200 Extra-Light（越大越细）

### 视频字号（1080p 必须放大）

- hero 中文 `clamp(72px, 6.5vw, 120px)`；hero 数字 `clamp(96px, 8vw, 144px)`
- kicker mono **37px**（章节内覆盖到 30px，letter-spacing 0.18em，accent 色）
- masthead 必须章节级覆盖放大：`.xx-scene .masthead .brand { font-size: 34px }` / `.issue { font-size: 26px }`
- 非 hero 文字统一 +20px 起；屏幕一屏一焦点（周报口播单步是短句节拍 ~30–90 字，见 script 规约）

### 动效

- 基础动画：`rise-in` / `fade` / `scale-punch` / `rule-grow` / `mask-reveal` / `letter-stagger`
- 多元素用**错峰 stagger**（2–3 卡 200–300ms；3–5 chip 100–150ms）
- **瑞士不是弹簧** —— 不用 spring/弹跳，默认 `ease-quart` / `ease-expo`
- 结构模式：VS 对比、旧→新转变（strike-through→箭头→accent 新词）、合并、pipeline 有固定表达，见 spec §4

### 章节 CSS 前缀（id 首字母）

`coldopen→.co-` · `llm-release→.lr-` · `price-war→.pw-` · `chip→.ch-` · `devices→.dv-` · `governance→.gv-` · `outro→.ou-`。keyframes 同前缀命名。新增章节按 `NN-<id> → .<id首字母>-` 规则。

---

## 章节技术约定

### 每章三文件

```
src/chapters/<NN>-<id>/
├── <Name>.tsx    # switch(step) 每步一个子组件，return <SceneN />
├── <Name>.css    # 视觉全放这里，类名 + keyframes 用章节前缀
└── narrations.ts # ★ step 数 + 口播文本唯一真相源
```

- `narrations.ts` 数组长度 = 该章 step 数；`.tsx` 分支数必须匹配；经 `chapters.ts` 注册自动关联
- narrations 一律用**模板字面量**（中文引号 `"` `"` 在双引号字符串里会截断）
- 数组元素必须是**纯字符串**：一个元素 = script.md 的一个节拍，可含多句、可用空行分段（对象形式 `{text, minHoldMs}` 已被 extract-narrations 移除）
- 空字符串 = silent step（不合成音频，运行时回退估算）
- 每 step 独占整屏，不滚动/弹窗/分页
- 场景根元素用 `.scene-pad`（居中）或 `.scene-pad xx-center`；`<Cmp step=... />` 由 registry 包一层 `.scene`

### 组件 / 钩子

- `Stage`（点击前进）、`ProgressBar`（**平时隐藏，悬浮出现**）、`AutoToggle`、`AutoStartGate`、`MaskReveal`
- `useStepper` 内有 `STORAGE_KEY` —— **每期 key 必带周次**：`presentation-cursor-weekly-<N>-v<X>`（例：weekly-5 首建 `presentation-cursor-weekly-5-v1`）。周次 `<N>` 每开新期都要设定；版本 `<X>` 在章节结构变动后 bump（v1→v2）。这样同时防两件事：(a) 跨期游标串位 —— 所有周次跑同一 localhost origin，localStorage 共享，key 不带周次会跳到别期的残留位置；(b) 结构改动后持久化游标落到不存在位置
- 音频播完 → auto-advance；无音频回退 `max(1500, len×250)ms`

### 其他

- spacing token 白名单 `--space-2/3/4/5/7/9`，**没有 `--space-6`**（需要 32px 写硬值或用 5/7 档）
- 禁止 `.tsx` 内 inline style 承载视觉（仅容器 flex 微调可容忍）
- 通用类：`.kicker` `.label-mono` `.card` `.chip` `.pull-quote` `.stat-row` `.rule` `.badge-mono` `.vs-divider`

---

## 反模式清单（项目级）

- ❌ 换主题 —— weekly 固定 swiss-ikb，不复用变体
- ❌ 圆角 / 渐变 / 阴影 / emoji / 衬线字体
- ❌ 跨章节共享 CSS 类名前缀
- ❌ 元素被非同类穿插时用 `nth-child`（用 `nth-of-type`）
- ❌ 双引号字符串里写中文引号（用模板字面量）
- ❌ script.md / narrations 里用半角标点 `,` `:` `?`（一律全角 `，` `：` `？`，保字幕切句正确）
- ❌ 同屏同步展示 N 项内容（1 项 = 1 step）
- ❌ 硬编码字体/颜色（用 token）
- ❌ 章节结构改动后不 bump STORAGE_KEY
- ❌ STORAGE_KEY 不带周次 / 复用上期 key（每期唯一：`presentation-cursor-weekly-<N>-v<X>`）

---

## 执行注意

- 并行 agent **≤3**；小任务直接主线程写（本环境派发常被网关故障打断）
- 第 1 章必做 anchor 验收，不跳过
- 素材多为周报长文，抓取后用结构化格式落 `article.md`，保留原文不删（双源原则）
